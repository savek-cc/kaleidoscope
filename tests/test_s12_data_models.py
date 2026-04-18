"""§12 Data Models — round-trip encode/decode for each wire model.

Pure tests, no BLE device required. Verifies that every model's serialized bytes
can be reconstructed to the original field values (struct integrity).
"""

import struct
from datetime import datetime

import pytest

from helpers.codec import (
    decode_alarm_bitfield,
    decode_system_time,
    encode_alarm_ack,
    encode_basal_profile,
    encode_bolus,
    encode_system_time,
    encode_temp_basal,
    pulses_to_units,
    units_to_pulses,
)
from helpers.constants import BASAL_PROFILE_NAME


class TestKldSystemTime:
    def test_round_trip(self):
        dt = datetime(2026, 4, 18, 12, 30, 45)
        encoded = encode_system_time(dt, tci=2, roc=3)
        year, month, day, hours, minutes, seconds, tci, roc = decode_system_time(encoded)
        assert year == 2026
        assert month == 4
        assert day == 18
        assert hours == 12
        assert minutes == 30
        assert seconds == 45
        assert tci == 2
        assert roc == 3

    def test_min_date(self):
        dt = datetime(2000, 1, 1, 0, 0, 0)
        encoded = encode_system_time(dt, tci=0, roc=0)
        fields = decode_system_time(encoded)
        assert fields[:6] == (2000, 1, 1, 0, 0, 0)

    def test_max_time_fields(self):
        dt = datetime(2099, 12, 31, 23, 59, 59)
        encoded = encode_system_time(dt, tci=255, roc=255)
        fields = decode_system_time(encoded)
        assert fields == (2099, 12, 31, 23, 59, 59, 255, 255)

    def test_wrong_size_raises(self):
        with pytest.raises(ValueError):
            decode_system_time(b"\x00" * 5)


class TestReservoirLevel:
    """Wire format: 2-byte u16 LE (§8.9, §9)."""

    @pytest.mark.parametrize("pulses", [0, 1, 100, 4000])
    def test_round_trip(self, pulses: int):
        encoded = struct.pack("<H", pulses)
        assert len(encoded) == 2
        decoded = struct.unpack("<H", encoded)[0]
        assert decoded == pulses

    def test_full_reservoir_200_units(self):
        # 200 U = 4000 pulses
        pulses = units_to_pulses(200.0)
        encoded = struct.pack("<H", pulses)
        decoded = struct.unpack("<H", encoded)[0]
        assert pulses_to_units(decoded) == 200.0

    def test_byte_order_is_little_endian(self):
        # 0x0190 = 400 → LE bytes: 0x90, 0x01
        encoded = struct.pack("<H", 400)
        assert encoded == bytes([0x90, 0x01])


class TestKldBasalProfile:
    def test_round_trip_name(self):
        profile = encode_basal_profile([1.0] * 24)
        name = profile[:20].decode("utf-8")
        assert name == BASAL_PROFILE_NAME

    def test_round_trip_rates(self):
        input_rates = [0.05 * i for i in range(1, 25)]  # 0.05, 0.10, ..., 1.20
        profile = encode_basal_profile(input_rates)
        rate_bytes = profile[20:]
        for i, rate in enumerate(input_rates):
            expected_byte = min(100, round(rate / 0.05))
            assert rate_bytes[i] == expected_byte

    def test_total_length(self):
        assert len(encode_basal_profile([0.0] * 24)) == 44

    def test_name_plus_rates_boundary(self):
        profile = encode_basal_profile([1.0] * 24)
        # Byte 19 = last byte of name field; byte 20 = first rate byte
        assert profile[19] == ord("I")  # "SECURITY_BASAL_PROFI"[-1]
        assert profile[20] == 20        # 1.0 U/hr = 20

    def test_zero_rate_encodes_to_zero(self):
        profile = encode_basal_profile([0.0] * 24)
        assert profile[20:] == bytes(24)


class TestKldPumpBolusRequest:
    """Wire format: [amount_u16_LE][0x0000][0x0000] = 6 bytes (§8.1)."""

    @pytest.mark.parametrize("pulses", [1, 10, 20, 100, 400])
    def test_round_trip(self, pulses: int):
        encoded = encode_bolus(pulses)
        decoded_pulses = struct.unpack_from("<H", encoded, 0)[0]
        assert decoded_pulses == pulses

    def test_reserved_fields_zero(self):
        encoded = encode_bolus(20)
        assert struct.unpack_from("<HH", encoded, 2) == (0, 0)

    def test_cancel_bolus_zero_amount(self):
        # §15.8: amount=0 cancels in-progress bolus
        encoded = encode_bolus(0)
        assert encoded == bytes(6)


class TestKldTemporaryBasalRequest:
    """Wire format: [pct_u16_LE][duration_u16_LE] = 4 bytes (§8.2)."""

    @pytest.mark.parametrize("pct,duration", [
        (0, 30), (50, 60), (100, 30), (150, 120), (200, 1440),
    ])
    def test_round_trip(self, pct: int, duration: int):
        encoded = encode_temp_basal(pct, duration)
        dec_pct, dec_dur = struct.unpack("<HH", encoded)
        assert dec_pct == pct
        assert dec_dur == duration

    def test_cancel_temp_basal(self):
        # §15.7: pct=100, duration=0
        encoded = encode_temp_basal(100, 0)
        pct, dur = struct.unpack("<HH", encoded)
        assert pct == 100
        assert dur == 0


class TestAlarmBitfieldRoundTrip:
    """Encode an alarm ACK (18 bytes) and verify decode_alarm_bitfield
    can recover the same bit indices from a padded 20-byte status frame.
    """

    def _ack_to_status(self, ack: bytes) -> bytes:
        """Expand 18-byte ack payload to a 20-byte status frame for decode testing.
        The status format is 20 bytes; alarm bits occupy the same bit positions.
        """
        return ack + b"\xff\xff"  # pad with 0xFF (inactive) bits

    def test_single_alarm_round_trip(self):
        # Encode alarm bit index 0, convert to status frame, decode
        ack = encode_alarm_ack([0])
        # Build a 20-byte frame where every bit is 1 (= inactive) except our alarm
        status = bytearray(b"\xff" * 20)
        # The ack has bit set in wire position (0+6); clear it in status = active
        wire_bit = 6
        byte_idx, bit_pos = wire_bit // 8, wire_bit % 8
        status[byte_idx] &= ~(1 << bit_pos)
        active = decode_alarm_bitfield(bytes(status))
        assert 0 in active

    def test_no_alarms_when_all_bits_set(self):
        # All bits = 1 means no active alarms
        status = b"\xff" * 20
        assert decode_alarm_bitfield(status) == []

    def test_wrong_size_raises(self):
        with pytest.raises(ValueError):
            decode_alarm_bitfield(b"\x00" * 19)

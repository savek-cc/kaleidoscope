"""§6 Wire Format Conventions — codec encode correctness tests.

All tests are pure (no BLE device required).
Expected byte sequences are derived from §6, §7, §8, and Appendix B of the manual.
"""

from datetime import datetime

import pytest

from helpers.codec import (
    encode_alarm_ack,
    encode_basal_profile,
    encode_bolus,
    encode_command,
    encode_system_time,
    encode_temp_basal,
)
from helpers.constants import (
    CMD_RING,
    CMD_UNLOCK_PUMP,
    RING_PAYLOAD,
    UNLOCK_TOKEN_BYTES,
)


class TestBolus:
    def test_1_unit_encodes_to_20_pulses(self):
        # 1.0 U = 20 pulses; 6-byte packet [amount_LE, 0x00 0x00, 0x00 0x00]
        result = encode_bolus(20)
        assert result == bytes([0x14, 0x00, 0x00, 0x00, 0x00, 0x00])

    def test_length_is_6_bytes(self):
        assert len(encode_bolus(1)) == 6

    def test_min_bolus_1_pulse(self):
        result = encode_bolus(1)
        assert result == bytes([0x01, 0x00, 0x00, 0x00, 0x00, 0x00])

    def test_max_bolus_400_pulses(self):
        # 400 = 0x0190 → LE: 0x90, 0x01
        result = encode_bolus(400)
        assert result == bytes([0x90, 0x01, 0x00, 0x00, 0x00, 0x00])

    def test_reserved_bytes_are_zero(self):
        result = encode_bolus(10)
        assert result[2:] == b"\x00\x00\x00\x00"


class TestTempBasal:
    def test_100pct_30min(self):
        # percentage=100=0x64, duration=30=0x1E; both u16 LE
        result = encode_temp_basal(100, 30)
        assert result == bytes([0x64, 0x00, 0x1E, 0x00])

    def test_length_is_4_bytes(self):
        assert len(encode_temp_basal(100, 30)) == 4

    def test_zero_pct_cancel(self):
        result = encode_temp_basal(0, 30)
        assert result[:2] == bytes([0x00, 0x00])

    def test_200pct_max(self):
        # 200 = 0xC8 → LE: 0xC8, 0x00
        result = encode_temp_basal(200, 60)
        assert result[:2] == bytes([0xC8, 0x00])

    def test_max_duration_1440_min(self):
        # 1440 = 0x05A0 → LE: 0xA0, 0x05
        result = encode_temp_basal(100, 1440)
        assert result[2:] == bytes([0xA0, 0x05])

    def test_cancel_temp_basal_wire(self):
        # §15.7: pct=100, duration=0 → [0x64, 0x00, 0x00, 0x00]
        result = encode_temp_basal(100, 0)
        assert result == bytes([0x64, 0x00, 0x00, 0x00])


class TestSystemTime:
    def test_exact_9_byte_sequence(self):
        # 2026-04-18 12:30:00, tci=1, roc=0
        # year=2026=0x07EA → LE [0xEA, 0x07]; month=4; day=18=0x12
        # hour=12=0x0C; min=30=0x1E; sec=0; tci=1; roc=0
        dt = datetime(2026, 4, 18, 12, 30, 0)
        result = encode_system_time(dt, tci=1, roc=0)
        expected = bytes([0xEA, 0x07, 0x04, 0x12, 0x0C, 0x1E, 0x00, 0x01, 0x00])
        assert result == expected

    def test_length_is_9_bytes(self):
        assert len(encode_system_time(datetime(2026, 1, 1, 0, 0, 0), 0, 0)) == 9

    def test_year_little_endian(self):
        dt = datetime(2026, 1, 1)
        result = encode_system_time(dt, 0, 0)
        year_from_bytes = int.from_bytes(result[0:2], "little")
        assert year_from_bytes == 2026

    def test_tci_and_roc_at_correct_offsets(self):
        dt = datetime(2026, 1, 1, 0, 0, 0)
        result = encode_system_time(dt, tci=3, roc=7)
        assert result[7] == 3
        assert result[8] == 7


class TestBasalProfile:
    def test_1_uhr_24_segments(self):
        # 1.0 U/hr → rate byte = round(1.0/0.05) = 20 = 0x14
        result = encode_basal_profile([1.0] * 24)
        assert len(result) == 44
        assert result[20:] == bytes([0x14] * 24)

    def test_profile_name_padded_to_20_bytes(self):
        result = encode_basal_profile([0.0] * 24)
        name_field = result[:20]
        assert name_field == b"SECURITY_BASAL_PROFI"

    def test_rate_byte_encoding(self):
        # §8.4: rate_byte = round(abs(rate) / 0.05), max 100
        rates = [0.05, 0.50, 1.00, 5.00] + [0.0] * 20
        result = encode_basal_profile(rates)
        rate_bytes = result[20:]
        assert rate_bytes[0] == 1    # 0.05 U/hr
        assert rate_bytes[1] == 10   # 0.50 U/hr
        assert rate_bytes[2] == 20   # 1.00 U/hr
        assert rate_bytes[3] == 100  # 5.00 U/hr (max)

    def test_rate_clamped_at_100(self):
        rates = [99.9] + [0.0] * 23
        result = encode_basal_profile(rates)
        assert result[20] == 100

    def test_wrong_segment_count_raises(self):
        with pytest.raises(ValueError):
            encode_basal_profile([1.0] * 23)


class TestCommandProtocol:
    def test_ring_exact_17_bytes(self):
        # §7 / §8.15: [0x03] + 16-byte beep pattern
        result = encode_command(CMD_RING, RING_PAYLOAD)
        expected = bytes([
            0x03,
            0x0F, 0x07, 0x0F, 0x07, 0x0F, 0x07, 0x0F,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        ])
        assert result == expected
        assert len(result) == 17

    def test_unlock_exact_17_bytes(self):
        # §7 / §14.2: [0x05] + "OTOphaYROmOgYMER" (16 ASCII bytes)
        result = encode_command(CMD_UNLOCK_PUMP, UNLOCK_TOKEN_BYTES)
        expected = bytes([
            0x05,
            0x4F, 0x54, 0x4F, 0x70, 0x68, 0x61, 0x59,
            0x52, 0x4F, 0x6D, 0x4F, 0x67, 0x59, 0x4D, 0x45, 0x52,
        ])
        assert result == expected
        assert len(result) == 17

    def test_command_id_is_first_byte(self):
        result = encode_command(0xAB, b"\x01\x02")
        assert result[0] == 0xAB

    def test_payload_appended_verbatim(self):
        payload = bytes([0x01, 0x02, 0x03])
        result = encode_command(0x01, payload)
        assert result[1:] == payload


class TestAlarmAck:
    def test_length_is_18_bytes(self):
        assert len(encode_alarm_ack([])) == 18

    def test_empty_ack_all_zeros(self):
        assert encode_alarm_ack([]) == bytes(18)

    def test_bit_index_0_maps_to_wire_bit_6(self):
        # alarm bit 0 → wire bit 6 → byte 0, bit 6
        result = encode_alarm_ack([0])
        assert result[0] == 0b01000000  # bit 6

    def test_bit_index_1_maps_to_wire_bit_7(self):
        result = encode_alarm_ack([1])
        assert result[0] == 0b10000000  # bit 7

    def test_bit_index_2_maps_to_byte_1_bit_0(self):
        # wire bit 8 = byte 1, bit 0
        result = encode_alarm_ack([2])
        assert result[1] == 0b00000001

    def test_multiple_alarms(self):
        result = encode_alarm_ack([0, 2])
        assert result[0] == 0b01000000
        assert result[1] == 0b00000001

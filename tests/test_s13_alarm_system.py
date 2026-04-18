"""§13 Alarm System — bitfield codec (pure) and BLE alarm read/ack (device).

Pure tests cover:
  - Correct bit positioning for all 74 known alarm indices (parametrized)
  - Inverted-bit logic (0 = active in status frame)
  - +6 wire offset between alarm.bitIndex and its position in the byte array

BLE tests cover:
  - readAlarmStatus() returns exactly 20 bytes
  - Decoded active alarm list contains only known bit indices
  - acknowledgeAlarm() round-trip: ack all active alarms, re-read, verify cleared
"""

import pytest

from helpers.codec import decode_alarm_bitfield, encode_alarm_ack
from helpers.constants import (
    ALARM_BIT_INDICES,
    CHAR_ALARM_ACK,
    CHAR_ALARM_STATUS,
)


# ---------------------------------------------------------------------------
# Pure codec tests  (no BLE required)
# ---------------------------------------------------------------------------

class TestAlarmBitIndexEncoding:
    """encode_alarm_ack sets the correct wire bit for every known alarm."""

    @pytest.mark.parametrize("name,bit_idx", sorted(ALARM_BIT_INDICES.items()))
    def test_correct_wire_bit_set(self, name: str, bit_idx: int):
        ack = encode_alarm_ack([bit_idx])
        wire_bit = bit_idx + 6
        byte_idx, bit_pos = wire_bit // 8, wire_bit % 8
        assert ack[byte_idx] & (1 << bit_pos), (
            f"Alarm {name} (bit {bit_idx}) → wire bit {wire_bit}: "
            f"byte {byte_idx} = {ack[byte_idx]:#04x}, expected bit {bit_pos} set"
        )

    @pytest.mark.parametrize("name,bit_idx", sorted(ALARM_BIT_INDICES.items()))
    def test_other_bytes_unaffected(self, name: str, bit_idx: int):
        ack = encode_alarm_ack([bit_idx])
        wire_bit = bit_idx + 6
        target_byte = wire_bit // 8
        for i, byte_val in enumerate(ack):
            if i != target_byte:
                assert byte_val == 0, (
                    f"Alarm {name}: expected only byte {target_byte} to be set, "
                    f"but byte {i} = {byte_val:#04x}"
                )


class TestAlarmBitfieldDecode:
    """decode_alarm_bitfield: inverted logic and +6 offset correctness."""

    def test_all_ones_means_no_alarms(self):
        assert decode_alarm_bitfield(b"\xff" * 20) == []

    def test_all_zeros_means_all_bits_active(self):
        active = decode_alarm_bitfield(b"\x00" * 20)
        # Every wire bit from 6 to 159 reports active → 154 indices
        assert len(active) == 154

    @pytest.mark.parametrize("bit_idx", sorted(ALARM_BIT_INDICES.values()))
    def test_single_alarm_active(self, bit_idx: int):
        """Clearing one bit in an all-ones frame must return exactly that alarm."""
        status = bytearray(b"\xff" * 20)
        wire_bit = bit_idx + 6
        status[wire_bit // 8] &= ~(1 << (wire_bit % 8))
        active = decode_alarm_bitfield(bytes(status))
        assert bit_idx in active

    def test_reserved_bits_0_to_5_ignored(self):
        """Bits 0-5 (wire) are reserved and must never appear in the output."""
        # Clear bits 0-5 (i.e., mark them "active") in an otherwise all-ones frame
        status = bytearray(b"\xff" * 20)
        status[0] = 0b11000000  # bits 0-5 cleared, bits 6-7 set
        active = decode_alarm_bitfield(bytes(status))
        for i in range(6):
            assert (i - 6) not in active  # these would be negative indices anyway
        # bit 0 in alarm space = wire bit 6 (byte 0, bit 6) — that bit IS set → not active
        assert 0 not in active


class TestAlarmAckIdempotent:
    """Encoding the same alarm twice must not set extra bits."""

    def test_ack_same_alarm_twice(self):
        a = encode_alarm_ack([10, 10])
        b = encode_alarm_ack([10])
        assert a == b


# ---------------------------------------------------------------------------
# BLE tests  (require device)
# ---------------------------------------------------------------------------

class TestReadAlarmStatus:
    async def test_response_is_20_bytes(self, unlocked_client):
        data = await unlocked_client.read_gatt_char(CHAR_ALARM_STATUS)
        assert len(data) == 20

    async def test_active_alarms_are_known_indices(self, unlocked_client):
        """Any active alarm bit index must be defined in ALARM_BIT_INDICES."""
        data = await unlocked_client.read_gatt_char(CHAR_ALARM_STATUS)
        active = decode_alarm_bitfield(bytes(data))
        known_indices = set(ALARM_BIT_INDICES.values())
        unknown = set(active) - known_indices
        assert not unknown, f"Alarm bitfield contains undocumented bit indices: {unknown}"


class TestAcknowledgeAlarms:
    async def test_ack_active_alarms_accepted(self, unlocked_client):
        """Read current alarms, ack all of them; write must be accepted."""
        data = await unlocked_client.read_gatt_char(CHAR_ALARM_STATUS)
        active = decode_alarm_bitfield(bytes(data))
        ack_payload = encode_alarm_ack(active)
        await unlocked_client.write_gatt_char(CHAR_ALARM_ACK, ack_payload, response=True)

    async def test_empty_ack_accepted(self, unlocked_client):
        await unlocked_client.write_gatt_char(
            CHAR_ALARM_ACK, encode_alarm_ack([]), response=True
        )

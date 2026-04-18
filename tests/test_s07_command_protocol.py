"""§7 Command Protocol — write each command packet to 0x2118 without error.

Requires a connected, unlocked device.
A successful BLE Write Response (no exception) is the acceptance criterion;
deeper side-effects (alarm bits) are covered in §13 and §14 tests.
"""

import pytest

from helpers.codec import encode_command
from helpers.constants import (
    CHAR_COMMAND_CHANNEL,
    CMD_CLEAR_PAIRING_KEY,
    CMD_RING,
    CMD_STORE_PAIRING_KEY,
    CMD_UNLOCK_PUMP,
    RING_PAYLOAD,
    UNLOCK_TOKEN_BYTES,
)


class TestCommandPacketFormat:
    """Verify the command packet structure before sending (pure, no BLE)."""

    def test_store_pairing_key_packet_size(self):
        pkt = encode_command(CMD_STORE_PAIRING_KEY, bytes(16))
        assert len(pkt) == 17

    def test_clear_pairing_key_packet_size(self):
        pkt = encode_command(CMD_CLEAR_PAIRING_KEY, bytes(16))
        assert len(pkt) == 17

    def test_ring_packet_size(self):
        pkt = encode_command(CMD_RING, RING_PAYLOAD)
        assert len(pkt) == 17

    def test_unlock_packet_size(self):
        pkt = encode_command(CMD_UNLOCK_PUMP, UNLOCK_TOKEN_BYTES)
        assert len(pkt) == 17


class TestCommandWrite:
    """Write each command to 0x2118 and assert no BLE exception is raised."""

    async def test_store_pairing_key(self, unlocked_client):
        pkt = encode_command(CMD_STORE_PAIRING_KEY, bytes(16))
        await unlocked_client.write_gatt_char(CHAR_COMMAND_CHANNEL, pkt, response=True)

    async def test_clear_pairing_key(self, unlocked_client):
        pkt = encode_command(CMD_CLEAR_PAIRING_KEY, bytes(16))
        await unlocked_client.write_gatt_char(CHAR_COMMAND_CHANNEL, pkt, response=True)

    async def test_ring(self, unlocked_client):
        pkt = encode_command(CMD_RING, RING_PAYLOAD)
        await unlocked_client.write_gatt_char(CHAR_COMMAND_CHANNEL, pkt, response=True)

    async def test_unlock(self, unlocked_client):
        """Re-sending the unlock command must be idempotent (§14.2)."""
        pkt = encode_command(CMD_UNLOCK_PUMP, UNLOCK_TOKEN_BYTES)
        await unlocked_client.write_gatt_char(CHAR_COMMAND_CHANNEL, pkt, response=True)

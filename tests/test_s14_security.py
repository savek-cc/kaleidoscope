"""§14 Security & Crypto Layer — unlock token, exclusive connection, pairing keys.

Mix of pure constant tests (no BLE) and BLE write acceptance tests.
"""

import pytest

from helpers.codec import encode_command
from helpers.constants import (
    CHAR_COMMAND_CHANNEL,
    CHAR_EXCLUSIVE_CONNECTION,
    CMD_CLEAR_PAIRING_KEY,
    CMD_STORE_PAIRING_KEY,
    CMD_UNLOCK_PUMP,
    UNLOCK_TOKEN,
    UNLOCK_TOKEN_BYTES,
)


# ---------------------------------------------------------------------------
# Pure token correctness tests  (no BLE required)
# ---------------------------------------------------------------------------

class TestUnlockToken:
    def test_token_string_value(self):
        assert UNLOCK_TOKEN == "OTOphaYROmOgYMER"

    def test_token_is_16_ascii_bytes(self):
        assert len(UNLOCK_TOKEN_BYTES) == 16
        assert UNLOCK_TOKEN_BYTES == b"OTOphaYROmOgYMER"

    def test_token_is_pure_ascii(self):
        UNLOCK_TOKEN.encode("ascii")  # raises if non-ASCII

    def test_unlock_command_id(self):
        assert CMD_UNLOCK_PUMP == 0x05

    def test_unlock_wire_format(self):
        """Full unlock packet: [0x05] + token = 17 bytes, exact hex match."""
        packet = encode_command(CMD_UNLOCK_PUMP, UNLOCK_TOKEN_BYTES)
        expected = bytes([
            0x05,
            0x4F, 0x54, 0x4F, 0x70, 0x68, 0x61, 0x59,
            0x52, 0x4F, 0x6D, 0x4F, 0x67, 0x59, 0x4D, 0x45, 0x52,
        ])
        assert packet == expected


class TestPairingKeyCommands:
    def test_store_pairing_key_id(self):
        assert CMD_STORE_PAIRING_KEY == 0x01

    def test_clear_pairing_key_id(self):
        assert CMD_CLEAR_PAIRING_KEY == 0x02

    def test_store_pairing_key_wire_format(self):
        """StorePairingKey: [0x01] + 16 zero bytes."""
        packet = encode_command(CMD_STORE_PAIRING_KEY, bytes(16))
        assert packet[0] == 0x01
        assert packet[1:] == bytes(16)

    def test_clear_pairing_key_wire_format(self):
        """ClearPairingKey: [0x02] + 16 zero bytes."""
        packet = encode_command(CMD_CLEAR_PAIRING_KEY, bytes(16))
        assert packet[0] == 0x02
        assert packet[1:] == bytes(16)


# ---------------------------------------------------------------------------
# BLE tests  (require device)
# ---------------------------------------------------------------------------

class TestExclusiveConnection:
    async def test_exclusive_connection_write_accepted(self, unlocked_client):
        """Writing [0x01] to 0x2114 must succeed (§8.10 / §14 layer 3)."""
        await unlocked_client.write_gatt_char(
            CHAR_EXCLUSIVE_CONNECTION, bytes([0x01]), response=True
        )

    async def test_only_valid_payload_is_0x01(self, unlocked_client):
        """Verify the canonical exclusive-connection payload is a single byte 0x01."""
        payload = bytes([0x01])
        assert len(payload) == 1
        assert payload[0] == 0x01
        await unlocked_client.write_gatt_char(
            CHAR_EXCLUSIVE_CONNECTION, payload, response=True
        )


class TestPairingKeyBLE:
    async def test_store_pairing_key_accepted(self, unlocked_client):
        pkt = encode_command(CMD_STORE_PAIRING_KEY, bytes(16))
        await unlocked_client.write_gatt_char(CHAR_COMMAND_CHANNEL, pkt, response=True)

    async def test_clear_pairing_key_accepted(self, unlocked_client):
        pkt = encode_command(CMD_CLEAR_PAIRING_KEY, bytes(16))
        await unlocked_client.write_gatt_char(CHAR_COMMAND_CHANNEL, pkt, response=True)

    async def test_store_then_clear_accepted(self, unlocked_client):
        store = encode_command(CMD_STORE_PAIRING_KEY, bytes(16))
        clear = encode_command(CMD_CLEAR_PAIRING_KEY, bytes(16))
        await unlocked_client.write_gatt_char(CHAR_COMMAND_CHANNEL, store, response=True)
        await unlocked_client.write_gatt_char(CHAR_COMMAND_CHANNEL, clear, response=True)


class TestUnlockBLE:
    async def test_unlock_idempotent(self, unlocked_client):
        """Sending the unlock command on an already-unlocked pump must be accepted."""
        pkt = encode_command(CMD_UNLOCK_PUMP, UNLOCK_TOKEN_BYTES)
        await unlocked_client.write_gatt_char(CHAR_COMMAND_CHANNEL, pkt, response=True)

"""§5 Connection State Machine — connection lifecycle and unlock flow tests.

Requires a BLE device. Session-scoped fixtures are used for the "already
connected" assertions; function-scoped BleakClient instances are used for
the disconnect/reconnect tests so the shared session client is unaffected.
"""

import asyncio

import pytest
from bleak import BleakClient

from helpers.codec import encode_command
from helpers.constants import (
    CHAR_COMMAND_CHANNEL,
    CHAR_DELIVERY_STATE,
    CMD_UNLOCK_PUMP,
    UNLOCK_TOKEN_BYTES,
    VALID_DELIVERY_STATES,
)


class TestConnectedState:
    """Verify the pump is reachable after the session fixture connects."""

    async def test_is_connected(self, ble_client):
        assert ble_client.is_connected

    async def test_can_read_after_connect(self, ble_client):
        """Reading a characteristic without unlock must succeed at the BLE layer
        (CONNECTED_AVAILABLE is reached, raw reads are permitted before unlock)."""
        data = await ble_client.read_gatt_char(CHAR_DELIVERY_STATE)
        assert isinstance(data, (bytes, bytearray))
        assert len(data) >= 1

    async def test_delivery_state_has_valid_value(self, ble_client):
        data = await ble_client.read_gatt_char(CHAR_DELIVERY_STATE)
        assert data[0] in VALID_DELIVERY_STATES


class TestUnlockTransition:
    """Verify pump is operational after the unlock command (§14.2 / §5)."""

    async def test_unlocked_client_is_connected(self, unlocked_client):
        assert unlocked_client.is_connected

    async def test_write_accepted_after_unlock(self, unlocked_client):
        """A protected write must succeed without raising after unlock.
        Re-sending the unlock token is idempotent per §14.2."""
        packet = encode_command(CMD_UNLOCK_PUMP, UNLOCK_TOKEN_BYTES)
        # Should not raise
        await unlocked_client.write_gatt_char(
            CHAR_COMMAND_CHANNEL, packet, response=True
        )

    async def test_state_readable_after_unlock(self, unlocked_client):
        data = await unlocked_client.read_gatt_char(CHAR_DELIVERY_STATE)
        assert data[0] in VALID_DELIVERY_STATES


class TestReconnect:
    """Disconnect a fresh client and verify reconnection restores full access.

    Uses a standalone BleakClient to avoid disturbing the session fixture.
    """

    async def test_disconnect_and_reconnect(self, request):
        address = request.config.getoption("--device-address")
        if not address:
            pytest.skip("--device-address required for reconnect test")

        client = BleakClient(address)
        await client.connect()
        assert client.is_connected

        await client.disconnect()
        assert not client.is_connected

        # Reconnect and verify operational
        await client.connect()
        assert client.is_connected

        data = await client.read_gatt_char(CHAR_DELIVERY_STATE)
        assert len(data) >= 1

        await client.disconnect()

    async def test_state_restored_after_reconnect(self, request):
        """After reconnect + re-unlock, delivery state read must return a valid value."""
        address = request.config.getoption("--device-address")
        if not address:
            pytest.skip("--device-address required for reconnect test")

        client = BleakClient(address)
        await client.connect()

        packet = encode_command(CMD_UNLOCK_PUMP, UNLOCK_TOKEN_BYTES)
        await client.write_gatt_char(CHAR_COMMAND_CHANNEL, packet, response=True)

        data = await client.read_gatt_char(CHAR_DELIVERY_STATE)
        assert data[0] in VALID_DELIVERY_STATES

        await client.disconnect()

"""Pytest configuration and BLE session fixtures for Kaleido protocol tests.

BLE fixture hierarchy
─────────────────────
  ble_client (session)        — raw connected BleakClient; disconnects at teardown
  unlocked_client (session)   — ble_client after unlock sequence (§14.2)
  reset_state (function)      — ensures STOPPED delivery state before each test
"""

import pytest
import pytest_asyncio
from bleak import BleakClient

from helpers.codec import encode_command
from helpers.constants import (
    CHAR_COMMAND_CHANNEL,
    CHAR_DELIVERY_STATE,
    CMD_UNLOCK_PUMP,
    DELIVERY_STATE,
    UNLOCK_TOKEN_BYTES,
)


# ---------------------------------------------------------------------------
# CLI options
# ---------------------------------------------------------------------------

def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--device-address",
        action="store",
        default=None,
        metavar="ADDRESS",
        help="BLE MAC address (or platform UUID on macOS) of the Kaleido pump.",
    )
    parser.addoption(
        "--device-name",
        action="store",
        default=None,
        metavar="NAME",
        help="BLE advertised name of the pump (alternative to --device-address).",
    )


def _resolve_device(config: pytest.Config) -> str:
    """Return the device address/name to connect to, or skip if none supplied."""
    address = config.getoption("--device-address")
    if address:
        return address
    name = config.getoption("--device-name")
    if name:
        return name
    pytest.skip("No BLE device specified — pass --device-address or --device-name")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="session")
async def ble_client(request: pytest.FixtureRequest) -> BleakClient:
    """Session-scoped connected BleakClient.

    Connects once for the entire test session and disconnects on teardown.
    Tests that require a connected-but-not-yet-unlocked client use this fixture.
    """
    address = _resolve_device(request.config)
    client = BleakClient(address)
    await client.connect()
    yield client
    if client.is_connected:
        await client.disconnect()


@pytest_asyncio.fixture(scope="session")
async def unlocked_client(ble_client: BleakClient) -> BleakClient:
    """Session-scoped BleakClient that has completed the unlock sequence (§14.2).

    Sends Command ID 0x05 with the hardcoded unlock token to characteristic
    0x2118, transitioning the pump from PENDING_UNLOCK → CONNECTED_AVAILABLE.
    """
    unlock_packet = encode_command(CMD_UNLOCK_PUMP, UNLOCK_TOKEN_BYTES)
    await ble_client.write_gatt_char(CHAR_COMMAND_CHANNEL, unlock_packet, response=True)
    return ble_client


@pytest_asyncio.fixture(scope="function")
async def reset_state(unlocked_client: BleakClient) -> None:
    """Function-scoped fixture: writes STOPPED delivery state before each test.

    Provides a clean slate by halting any in-progress delivery.
    Tests that need a different initial state should transition from STOPPED
    themselves rather than relying on prior test side-effects.
    """
    stopped = bytes([DELIVERY_STATE["STOPPED"]])
    await unlocked_client.write_gatt_char(CHAR_DELIVERY_STATE, stopped, response=True)
    yield

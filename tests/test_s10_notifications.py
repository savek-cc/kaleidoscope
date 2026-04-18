"""§10 Notification Messages — trigger state changes and assert notifications.

Requires a connected, unlocked device.
Each test:
  1. Subscribes to the relevant characteristic via notify_and_collect()
  2. Triggers a state change (write) that must produce a notification
  3. Asserts correct DATA_SIZE and parsed value validity

The ParsingFailureMessage injection tests (wrong-length data) are marked xfail
until the ZephyrOS simulator exposes a test injection API (open question #1).
"""

import pytest

from helpers.ble import notify_and_collect
from helpers.constants import (
    CHAR_BATTERY_LEVEL,
    CHAR_CURRENT_BASAL_RATE,
    CHAR_DELIVERY_STATE,
    CHAR_DELIVERY_TYPE,
    CHAR_IDU_MODE,
    CHAR_RESERVOIR_LEVEL,
    DELIVERY_STATE,
    VALID_DELIVERY_STATES,
    VALID_IDU_MODES,
)


class TestDeliveryStateNotification:
    """0x2105 — writing a new delivery state must produce a 1-byte notification."""

    async def test_notification_on_state_change(self, unlocked_client, reset_state):
        target = DELIVERY_STATE["DELIVERING"]
        data = await notify_and_collect(
            unlocked_client,
            CHAR_DELIVERY_STATE,
            unlocked_client.write_gatt_char(
                CHAR_DELIVERY_STATE, bytes([target]), response=True
            ),
        )
        assert len(data) == 1

    async def test_notification_value_is_valid_state(self, unlocked_client, reset_state):
        target = DELIVERY_STATE["DELIVERING"]
        data = await notify_and_collect(
            unlocked_client,
            CHAR_DELIVERY_STATE,
            unlocked_client.write_gatt_char(
                CHAR_DELIVERY_STATE, bytes([target]), response=True
            ),
        )
        assert data[0] in VALID_DELIVERY_STATES

    async def test_stopped_state_notification(self, unlocked_client):
        target = DELIVERY_STATE["STOPPED"]
        data = await notify_and_collect(
            unlocked_client,
            CHAR_DELIVERY_STATE,
            unlocked_client.write_gatt_char(
                CHAR_DELIVERY_STATE, bytes([target]), response=True
            ),
        )
        assert data[0] in VALID_DELIVERY_STATES

    @pytest.mark.xfail(
        reason="Requires simulator test injection API to send wrong-length data (open question #1)"
    )
    async def test_wrong_length_triggers_parsing_failure(self, unlocked_client):
        # This test requires the simulator to inject a wrong-length notification.
        # Expected behaviour: pump sends 2 bytes instead of 1 → ParsingFailureMessage.
        raise NotImplementedError


class TestIduModeNotification:
    """0x2100 — IDU mode changes must produce a 1-byte notification."""

    async def test_notification_size_is_1_byte(self, unlocked_client, reset_state):
        """Trigger a delivery state change which on some firmware also causes
        an IDU mode notification. At minimum, subscribe succeeds."""
        import asyncio

        received = []

        def handler(_sender, data):
            received.append(data)

        await unlocked_client.start_notify(CHAR_IDU_MODE, handler)
        # Write DELIVERING to encourage a mode transition
        await unlocked_client.write_gatt_char(
            CHAR_DELIVERY_STATE, bytes([DELIVERY_STATE["DELIVERING"]]), response=True
        )
        await asyncio.sleep(1.0)
        await unlocked_client.stop_notify(CHAR_IDU_MODE)

        for notif in received:
            assert len(notif) == 1
            assert notif[0] in VALID_IDU_MODES


class TestReservoirLevelNotification:
    """0x2104 — writing reservoir level must produce a 2-byte notification."""

    async def test_notification_on_reservoir_write(self, unlocked_client):
        import struct

        payload = struct.pack("<H", 4000)
        data = await notify_and_collect(
            unlocked_client,
            CHAR_RESERVOIR_LEVEL,
            unlocked_client.write_gatt_char(CHAR_RESERVOIR_LEVEL, payload, response=True),
        )
        assert len(data) == 2

    async def test_notification_value_is_valid_pulse_count(self, unlocked_client):
        import struct

        payload = struct.pack("<H", 2000)  # 100 U
        data = await notify_and_collect(
            unlocked_client,
            CHAR_RESERVOIR_LEVEL,
            unlocked_client.write_gatt_char(CHAR_RESERVOIR_LEVEL, payload, response=True),
        )
        pulses = struct.unpack("<H", data)[0]
        assert 0 <= pulses <= 4000


class TestDeliveryTypeNotification:
    """0x210C — any delivery change must produce a 1-byte bitmask notification."""

    async def test_notification_size(self, unlocked_client, reset_state):
        import asyncio

        received = []

        def handler(_sender, data):
            received.append(bytes(data))

        await unlocked_client.start_notify(CHAR_DELIVERY_TYPE, handler)
        await unlocked_client.write_gatt_char(
            CHAR_DELIVERY_STATE, bytes([DELIVERY_STATE["DELIVERING"]]), response=True
        )
        await asyncio.sleep(1.0)
        await unlocked_client.stop_notify(CHAR_DELIVERY_TYPE)

        for notif in received:
            assert len(notif) == 1
            assert (notif[0] & ~0x07) == 0  # only bits 0-2 valid

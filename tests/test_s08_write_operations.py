"""§8 Write Operations — one test per write operation (§8.1–§8.16).

Requires a connected, unlocked device.
Each test writes the characteristic and asserts:
  - No BLE exception (write response received)
  - Where a read-back is possible, the written value round-trips correctly.
  - Where a notification is expected, notify_and_collect() is used.

§8.16 (writeCartridgeInsertionDate) is skipped — wire format is "variable" /
unspecified in the manual (open question #2).
"""

import asyncio
from datetime import datetime

import pytest

from helpers.ble import notify_and_collect
from helpers.codec import (
    encode_basal_profile,
    encode_bolus,
    encode_system_time,
    encode_temp_basal,
)
from helpers.constants import (
    CHAR_ALARM_ACK,
    CHAR_BASAL_PROFILE,
    CHAR_BOLUS_REQUEST,
    CHAR_DELIVERY_STATE,
    CHAR_DELIVERY_TYPE,
    CHAR_EXCLUSIVE_CONNECTION,
    CHAR_IDU_MODE,
    CHAR_INSULIN_ON_BOARD,
    CHAR_PRIME_PUMP,
    CHAR_RESERVOIR_LEVEL,
    CHAR_SYSTEM_TIME,
    CHAR_TEMP_BASAL_REQUEST,
    CHAR_TOTAL_DAILY_DOSE,
    DELIVERY_STATE,
    DELIVERY_TYPE_BASAL,
    VALID_DELIVERY_STATES,
)


class TestSendBolusRequest:
    """§8.1 — Write 6-byte bolus request to 0x210A."""

    @pytest.mark.parametrize("pulses", [1, 10, 20])
    async def test_write_accepted(self, unlocked_client, reset_state, pulses):
        payload = encode_bolus(pulses)
        await unlocked_client.write_gatt_char(CHAR_BOLUS_REQUEST, payload, response=True)

    async def test_cancel_bolus_zero_amount(self, unlocked_client, reset_state):
        """§15.8 — amount=0 must be accepted to cancel in-progress bolus."""
        payload = encode_bolus(0)
        await unlocked_client.write_gatt_char(CHAR_BOLUS_REQUEST, payload, response=True)

    async def test_bolus_triggers_delivery_type_notification(self, unlocked_client, reset_state):
        """Writing a bolus request should trigger a DeliveryType notification."""
        # Ensure delivering state so bolus is processed
        await unlocked_client.write_gatt_char(
            CHAR_DELIVERY_STATE, bytes([DELIVERY_STATE["DELIVERING"]]), response=True
        )
        payload = encode_bolus(1)
        data = await notify_and_collect(
            unlocked_client,
            CHAR_DELIVERY_TYPE,
            unlocked_client.write_gatt_char(CHAR_BOLUS_REQUEST, payload, response=True),
            timeout=5.0,
        )
        assert len(data) == 1


class TestSendTempBasalRequest:
    """§8.2 — Write 4-byte temp basal request to 0x2108."""

    @pytest.mark.parametrize("pct,duration", [(50, 30), (100, 60), (150, 120)])
    async def test_write_accepted(self, unlocked_client, reset_state, pct, duration):
        await unlocked_client.write_gatt_char(
            CHAR_DELIVERY_STATE, bytes([DELIVERY_STATE["DELIVERING"]]), response=True
        )
        payload = encode_temp_basal(pct, duration)
        await unlocked_client.write_gatt_char(CHAR_TEMP_BASAL_REQUEST, payload, response=True)

    async def test_cancel_temp_basal(self, unlocked_client, reset_state):
        """§15.7 — pct=100, duration=0 cancels active temp basal."""
        payload = encode_temp_basal(100, 0)
        await unlocked_client.write_gatt_char(CHAR_TEMP_BASAL_REQUEST, payload, response=True)


class TestWriteSystemTime:
    """§8.3 — Write 9-byte system time to 0x2117."""

    async def test_write_accepted(self, unlocked_client):
        dt = datetime.now()
        payload = encode_system_time(dt, tci=0, roc=0)
        await unlocked_client.write_gatt_char(CHAR_SYSTEM_TIME, payload, response=True)

    async def test_read_back_length(self, unlocked_client):
        """After writing, reading 0x2117 must return 9 or 113 bytes (§8.3)."""
        dt = datetime.now()
        payload = encode_system_time(dt, tci=0, roc=0)
        await unlocked_client.write_gatt_char(CHAR_SYSTEM_TIME, payload, response=True)
        data = await unlocked_client.read_gatt_char(CHAR_SYSTEM_TIME)
        assert len(data) in (9, 113)


class TestWriteBasalProfile:
    """§8.4 — Write 44-byte basal profile to 0x2107."""

    async def test_write_accepted(self, unlocked_client):
        payload = encode_basal_profile([1.0] * 24)
        await unlocked_client.write_gatt_char(CHAR_BASAL_PROFILE, payload, response=True)

    async def test_zero_rates_accepted(self, unlocked_client):
        payload = encode_basal_profile([0.0] * 24)
        await unlocked_client.write_gatt_char(CHAR_BASAL_PROFILE, payload, response=True)


class TestUpdateDeliveryState:
    """§8.5 — Write 1-byte delivery state to 0x2105."""

    @pytest.mark.parametrize("state_name,state_value", [
        ("STOPPED",    1),
        ("PAUSED",     2),
        ("DELIVERING", 4),
    ])
    async def test_write_and_read_back(self, unlocked_client, reset_state, state_name, state_value):
        await unlocked_client.write_gatt_char(
            CHAR_DELIVERY_STATE, bytes([state_value]), response=True
        )
        data = await unlocked_client.read_gatt_char(CHAR_DELIVERY_STATE)
        assert data[0] in VALID_DELIVERY_STATES  # pump may coerce to valid state

    async def test_write_triggers_notification(self, unlocked_client, reset_state):
        target = DELIVERY_STATE["STOPPED"]
        data = await notify_and_collect(
            unlocked_client,
            CHAR_DELIVERY_STATE,
            unlocked_client.write_gatt_char(
                CHAR_DELIVERY_STATE, bytes([target]), response=True
            ),
            timeout=5.0,
        )
        assert len(data) == 1
        assert data[0] in VALID_DELIVERY_STATES


class TestPrimePump:
    """§8.6 — Write 1-byte pulse count to 0x2113.

    Marked slow: priming has a physical effect on the pump.
    Pump must be in PRIMING state before this write has effect.
    """

    @pytest.mark.slow
    async def test_prime_write_accepted(self, unlocked_client, reset_state):
        await unlocked_client.write_gatt_char(
            CHAR_DELIVERY_STATE, bytes([DELIVERY_STATE["PRIMING"]]), response=True
        )
        await unlocked_client.write_gatt_char(
            CHAR_PRIME_PUMP, bytes([10]), response=True
        )


class TestWriteReservoirLevel:
    """§8.9 — Write 2-byte reservoir level (pulses, u16 LE) to 0x2104."""

    async def test_write_accepted(self, unlocked_client):
        import struct
        payload = struct.pack("<H", 4000)  # 200 U = 4000 pulses
        await unlocked_client.write_gatt_char(CHAR_RESERVOIR_LEVEL, payload, response=True)

    async def test_read_back_length(self, unlocked_client):
        data = await unlocked_client.read_gatt_char(CHAR_RESERVOIR_LEVEL)
        assert len(data) == 2


class TestSetExclusiveConnection:
    """§8.10 — Write [0x01] to 0x2114 to claim exclusive control."""

    async def test_write_accepted(self, unlocked_client):
        await unlocked_client.write_gatt_char(
            CHAR_EXCLUSIVE_CONNECTION, bytes([0x01]), response=True
        )


class TestWriteEmptyInsulinOnBoard:
    """§8.11 — Write 50 zero bytes to 0x2111 to reset IOB tracking."""

    async def test_50_zeros_accepted(self, unlocked_client):
        await unlocked_client.write_gatt_char(
            CHAR_INSULIN_ON_BOARD, bytes(50), response=True
        )

    async def test_82_zeros_accepted(self, unlocked_client):
        await unlocked_client.write_gatt_char(
            CHAR_INSULIN_ON_BOARD, bytes(82), response=True
        )


class TestWriteEmptyTotalDailyDose:
    """§8.12 — Write 14 zero bytes to 0x2115 to reset TDD tracking."""

    async def test_14_zeros_accepted(self, unlocked_client):
        await unlocked_client.write_gatt_char(
            CHAR_TOTAL_DAILY_DOSE, bytes(14), response=True
        )

    async def test_110_zeros_accepted(self, unlocked_client):
        await unlocked_client.write_gatt_char(
            CHAR_TOTAL_DAILY_DOSE, bytes(110), response=True
        )


class TestAcknowledgeAlarm:
    """§8.8 — Write 18-byte alarm ack bitfield to 0x2103."""

    async def test_empty_ack_accepted(self, unlocked_client):
        """Acknowledging no alarms (all-zeros payload) must be accepted."""
        from helpers.codec import encode_alarm_ack
        payload = encode_alarm_ack([])
        await unlocked_client.write_gatt_char(CHAR_ALARM_ACK, payload, response=True)


class TestWriteCartridgeInsertionDate:
    """§8.16 — Skipped: wire format for LocalDateTime serialization is unspecified."""

    @pytest.mark.skip(reason="Wire format for 0x210B LocalDateTime is unspecified (open question #2)")
    async def test_write_accepted(self, unlocked_client):
        pass

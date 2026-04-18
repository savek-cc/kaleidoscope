"""§9 Read Operations — read each readable characteristic and validate response.

Requires a connected, unlocked device.
For each characteristic, assertions cover:
  - Correct response byte length (DATA_SIZE per §10)
  - Value falls within valid enum range where applicable
"""

import struct

import pytest

from helpers.constants import (
    CHAR_ALARM_STATUS,
    CHAR_BATTERY_LEVEL,
    CHAR_CARTRIDGE_DATE,
    CHAR_CURRENT_BASAL_RATE,
    CHAR_DELIVERY_STATE,
    CHAR_DELIVERY_TYPE,
    CHAR_IDU_MODE,
    CHAR_RESERVOIR_LEVEL,
    CHAR_SYSTEM_TIME,
    CHAR_TEMP_BASAL_TIME_LEFT,
    VALID_DELIVERY_STATES,
    VALID_IDU_MODES,
)


class TestReadIduMode:
    """readIduMode() → 0x2100 → 1 byte → KldIduMode enum."""

    async def test_length(self, unlocked_client):
        data = await unlocked_client.read_gatt_char(CHAR_IDU_MODE)
        assert len(data) == 1

    async def test_valid_enum_value(self, unlocked_client):
        data = await unlocked_client.read_gatt_char(CHAR_IDU_MODE)
        assert data[0] in VALID_IDU_MODES


class TestReadDeliveryState:
    """readDeliveryState() → 0x2105 → 1 byte → KldDeliveryState enum."""

    async def test_length(self, unlocked_client):
        data = await unlocked_client.read_gatt_char(CHAR_DELIVERY_STATE)
        assert len(data) == 1

    async def test_valid_enum_value(self, unlocked_client):
        data = await unlocked_client.read_gatt_char(CHAR_DELIVERY_STATE)
        assert data[0] in VALID_DELIVERY_STATES


class TestReadDeliveryType:
    """readDeliveryType() → 0x210C → 1 byte → KldDeliveryType bitmask."""

    async def test_length(self, unlocked_client):
        data = await unlocked_client.read_gatt_char(CHAR_DELIVERY_TYPE)
        assert len(data) == 1

    async def test_only_valid_bits_set(self, unlocked_client):
        """Byte value must only use bits 0-2 (basal, temp, bolus)."""
        data = await unlocked_client.read_gatt_char(CHAR_DELIVERY_TYPE)
        assert (data[0] & ~0x07) == 0, f"Unexpected bits set in DeliveryType: {data[0]:#04x}"


class TestReadReservoirLevel:
    """readReservoirLevel() → 0x2104 → 2 bytes u16 LE → pulses."""

    async def test_length(self, unlocked_client):
        data = await unlocked_client.read_gatt_char(CHAR_RESERVOIR_LEVEL)
        assert len(data) == 2

    async def test_value_in_range(self, unlocked_client):
        data = await unlocked_client.read_gatt_char(CHAR_RESERVOIR_LEVEL)
        pulses = struct.unpack("<H", data)[0]
        assert 0 <= pulses <= 4000, f"Reservoir {pulses} pulses out of range [0, 4000]"


class TestReadCurrentBasalRate:
    """readCurrentBasalRate() → 0x2112 → 2 bytes u16 LE → pulses/hr."""

    async def test_length(self, unlocked_client):
        data = await unlocked_client.read_gatt_char(CHAR_CURRENT_BASAL_RATE)
        assert len(data) == 2

    async def test_rate_in_range(self, unlocked_client):
        data = await unlocked_client.read_gatt_char(CHAR_CURRENT_BASAL_RATE)
        pulses = struct.unpack("<H", data)[0]
        # Max 5.0 U/hr = 100 pulses/hr; 0 is valid (stopped/idle)
        assert 0 <= pulses <= 100, f"Basal rate {pulses} pulses/hr out of range [0, 100]"


class TestReadBatteryLevel:
    """readBatteryLevel() → 0x2A19 → 1 byte → percentage."""

    async def test_length(self, unlocked_client):
        data = await unlocked_client.read_gatt_char(CHAR_BATTERY_LEVEL)
        assert len(data) == 1

    async def test_value_is_percentage(self, unlocked_client):
        data = await unlocked_client.read_gatt_char(CHAR_BATTERY_LEVEL)
        assert 0 <= data[0] <= 100, f"Battery level {data[0]}% out of range"


class TestReadAlarmStatus:
    """readAlarmStatus() → 0x2101 → 20 bytes bitfield."""

    async def test_length(self, unlocked_client):
        data = await unlocked_client.read_gatt_char(CHAR_ALARM_STATUS)
        assert len(data) == 20

    async def test_decode_does_not_raise(self, unlocked_client):
        from helpers.codec import decode_alarm_bitfield
        data = await unlocked_client.read_gatt_char(CHAR_ALARM_STATUS)
        active = decode_alarm_bitfield(bytes(data))
        assert isinstance(active, list)


class TestReadSystemTime:
    """readSystemTime() → 0x2117 → 9 bytes (or 113)."""

    async def test_length(self, unlocked_client):
        data = await unlocked_client.read_gatt_char(CHAR_SYSTEM_TIME)
        assert len(data) in (9, 113)

    async def test_year_is_plausible(self, unlocked_client):
        data = await unlocked_client.read_gatt_char(CHAR_SYSTEM_TIME)
        year = struct.unpack_from("<H", data, 0)[0]
        assert 2020 <= year <= 2100, f"Year {year} looks wrong"


class TestReadTempBasalTimeLeft:
    """readTemporaryBasalTimeLeft() → 0x2109 → 2 bytes LE → minutes."""

    async def test_length(self, unlocked_client):
        data = await unlocked_client.read_gatt_char(CHAR_TEMP_BASAL_TIME_LEFT)
        assert len(data) == 2

    async def test_duration_in_range(self, unlocked_client):
        data = await unlocked_client.read_gatt_char(CHAR_TEMP_BASAL_TIME_LEFT)
        minutes = struct.unpack("<H", data)[0]
        assert 0 <= minutes <= 1440, f"Temp basal time left {minutes} min out of range"


class TestReadCartridgeInsertionDate:
    """readCartridgeInsertionDate() → 0x210B — variable format, just verify non-empty."""

    async def test_returns_data(self, unlocked_client):
        data = await unlocked_client.read_gatt_char(CHAR_CARTRIDGE_DATE)
        assert len(data) >= 1

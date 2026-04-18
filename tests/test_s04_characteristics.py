"""§4 BLE Service & Characteristics — service discovery and UUID presence tests.

Requires a connected BLE device (--device-address or --device-name).
"""

import pytest

from helpers.constants import (
    ALL_CHARACTERISTIC_UUIDS,
    SERVICE_UUID_PREFIX,
    CHAR_IDU_MODE,
    CHAR_ALARM_STATUS,
    CHAR_RESERVOIR_LEVEL,
    CHAR_DELIVERY_STATE,
    CHAR_TEMP_BASAL_TIME_LEFT,
    CHAR_DELIVERY_TYPE,
    CHAR_CURRENT_BASAL_RATE,
    CHAR_BATTERY_LEVEL,
)

# Characteristics that support notifications (§4, §10)
NOTIFY_CHARACTERISTICS = [
    CHAR_IDU_MODE,
    CHAR_ALARM_STATUS,
    CHAR_RESERVOIR_LEVEL,
    CHAR_DELIVERY_STATE,
    CHAR_TEMP_BASAL_TIME_LEFT,
    CHAR_DELIVERY_TYPE,
    CHAR_CURRENT_BASAL_RATE,
    CHAR_BATTERY_LEVEL,
]


class TestServiceDiscovery:
    async def test_client_is_connected(self, ble_client):
        assert ble_client.is_connected

    async def test_services_discovered(self, ble_client):
        services = ble_client.services
        assert services is not None

    async def test_kaleido_service_uuid_prefix(self, ble_client):
        """The Kaleido service UUID must start with the 812321XX base pattern."""
        uuids = [str(s.uuid).lower() for s in ble_client.services]
        kaleido = [u for u in uuids if u.startswith(SERVICE_UUID_PREFIX.lower())]
        assert len(kaleido) >= 1, f"No service with prefix {SERVICE_UUID_PREFIX!r} found; got {uuids}"


class TestCharacteristicPresence:
    async def test_all_20_characteristics_present(self, ble_client):
        """Every UUID in Appendix A must be discoverable on the connected device."""
        found: set[str] = set()
        for service in ble_client.services:
            for char in service.characteristics:
                found.add(str(char.uuid).lower())

        missing = {u.lower() for u in ALL_CHARACTERISTIC_UUIDS} - found
        assert not missing, f"Missing characteristics: {missing}"

    @pytest.mark.parametrize("uuid", sorted(ALL_CHARACTERISTIC_UUIDS))
    async def test_characteristic_uuid_present(self, ble_client, uuid: str):
        found = {
            str(char.uuid).lower()
            for service in ble_client.services
            for char in service.characteristics
        }
        assert uuid.lower() in found

    @pytest.mark.parametrize("uuid", NOTIFY_CHARACTERISTICS)
    async def test_notify_characteristic_subscribable(self, ble_client, uuid: str):
        """start_notify / stop_notify must not raise for all notify chars."""
        await ble_client.start_notify(uuid, lambda _s, _d: None)
        await ble_client.stop_notify(uuid)

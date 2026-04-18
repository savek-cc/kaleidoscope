"""§11 Enumerations & Constants — all enum values and bitmask correctness.

Pure tests, no BLE device required.
"""

import pytest

from helpers.constants import (
    CONNECTION_STATE,
    DELIVERY_STATE,
    DELIVERY_STATE_BY_VALUE,
    DELIVERY_TYPE_BASAL,
    DELIVERY_TYPE_BOLUS,
    DELIVERY_TYPE_TEMP_BASAL,
    IDU_MODE,
    IDU_MODE_BY_VALUE,
    VALID_DELIVERY_STATES,
    VALID_IDU_MODES,
)


class TestKldIduMode:
    @pytest.mark.parametrize("name,value", [
        ("BOOT",     0),
        ("IDLE",     1),
        ("ALARM",    2),
        ("DELIVERY", 3),
        ("SHUTDOWN", 4),
    ])
    def test_value(self, name: str, value: int):
        assert IDU_MODE[name] == value

    def test_all_5_modes_defined(self):
        assert len(IDU_MODE) == 5

    def test_reverse_lookup(self):
        assert IDU_MODE_BY_VALUE[3] == "DELIVERY"

    def test_valid_set_contains_all_values(self):
        assert VALID_IDU_MODES == frozenset(IDU_MODE.values())


class TestKldDeliveryState:
    @pytest.mark.parametrize("name,value", [
        ("UNDEFINED",  0),
        ("STOPPED",    1),
        ("PAUSED",     2),
        ("PRIMING",    3),
        ("DELIVERING", 4),
    ])
    def test_value(self, name: str, value: int):
        assert DELIVERY_STATE[name] == value

    def test_all_5_states_defined(self):
        assert len(DELIVERY_STATE) == 5

    def test_reverse_lookup(self):
        assert DELIVERY_STATE_BY_VALUE[1] == "STOPPED"

    def test_valid_set_contains_all_values(self):
        assert VALID_DELIVERY_STATES == frozenset(DELIVERY_STATE.values())


class TestKldDeliveryTypeBitmask:
    def test_basal_bit(self):
        assert DELIVERY_TYPE_BASAL == 0x01

    def test_temp_basal_bit(self):
        assert DELIVERY_TYPE_TEMP_BASAL == 0x02

    def test_bolus_bit(self):
        assert DELIVERY_TYPE_BOLUS == 0x04

    def test_basal_plus_bolus_combined(self):
        # §11 example: 0x05 = basal + bolus
        combined = DELIVERY_TYPE_BASAL | DELIVERY_TYPE_BOLUS
        assert combined == 0x05

    def test_all_three_combined(self):
        all_active = DELIVERY_TYPE_BASAL | DELIVERY_TYPE_TEMP_BASAL | DELIVERY_TYPE_BOLUS
        assert all_active == 0x07

    def test_bits_are_distinct(self):
        bits = [DELIVERY_TYPE_BASAL, DELIVERY_TYPE_TEMP_BASAL, DELIVERY_TYPE_BOLUS]
        # No two bits overlap
        for i, a in enumerate(bits):
            for b in bits[i + 1:]:
                assert (a & b) == 0

    @pytest.mark.parametrize("raw,expected_basal,expected_temp,expected_bolus", [
        (0x01, True,  False, False),
        (0x02, False, True,  False),
        (0x04, False, False, True),
        (0x05, True,  False, True),
        (0x07, True,  True,  True),
        (0x00, False, False, False),
    ])
    def test_bitmask_decode(self, raw, expected_basal, expected_temp, expected_bolus):
        assert bool(raw & DELIVERY_TYPE_BASAL)      == expected_basal
        assert bool(raw & DELIVERY_TYPE_TEMP_BASAL) == expected_temp
        assert bool(raw & DELIVERY_TYPE_BOLUS)      == expected_bolus


class TestConnectionState:
    @pytest.mark.parametrize("name,value", [
        ("DISCONNECTED",                        0),
        ("CONNECTING",                          1),
        ("CONNECTED_REGISTERING_STATE_CHANGES", 2),
        ("CONNECTED_DISCOVERING_SERVICES",      3),
        ("CONNECTED_REGISTERING_PUSH",          4),
        ("CONNECTED_AVAILABLE",                 5),
        ("DISCONNECTING",                       6),
        ("PENDING_UNLOCK",                      7),
    ])
    def test_value(self, name: str, value: int):
        assert CONNECTION_STATE[name] == value

    def test_all_8_states_defined(self):
        assert len(CONNECTION_STATE) == 8

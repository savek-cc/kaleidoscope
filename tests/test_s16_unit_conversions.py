"""§16 Insulin Unit Conversions — pulse/unit table and basal rate byte encoding.

Pure tests, no BLE device required.
"""

import pytest

from helpers.codec import pulses_to_units, units_to_pulses, encode_basal_profile


class TestPulsesToUnits:
    @pytest.mark.parametrize("pulses,expected_units", [
        (1,   0.05),
        (10,  0.5),
        (20,  1.0),
        (100, 5.0),
        (200, 10.0),
        (400, 20.0),
    ])
    def test_table(self, pulses: int, expected_units: float):
        assert pulses_to_units(pulses) == expected_units

    def test_zero_pulses(self):
        assert pulses_to_units(0) == 0.0

    def test_result_rounded_to_3_decimal_places(self):
        # 3 pulses * 0.05 = 0.15 (exact), no rounding issue
        assert pulses_to_units(3) == 0.15

    def test_large_value_precision(self):
        # 399 pulses = 19.95 U
        assert pulses_to_units(399) == 19.95


class TestUnitsToPulses:
    @pytest.mark.parametrize("units,expected_pulses", [
        (0.05,  1),
        (0.5,  10),
        (1.0,  20),
        (5.0, 100),
        (10.0, 200),
        (20.0, 400),
    ])
    def test_table(self, units: float, expected_pulses: int):
        assert units_to_pulses(units) == expected_pulses

    def test_zero_units(self):
        assert units_to_pulses(0.0) == 0

    def test_rounds_to_nearest_pulse(self):
        # 0.051 U / 0.05 = 1.02 → rounds to 1
        assert units_to_pulses(0.051) == 1
        # 0.074 U / 0.05 = 1.48 → rounds to 1
        assert units_to_pulses(0.074) == 1
        # 0.076 U / 0.05 = 1.52 → rounds to 2
        assert units_to_pulses(0.076) == 2


class TestRoundTrip:
    @pytest.mark.parametrize("pulses", [1, 10, 20, 100, 200, 400])
    def test_pulses_round_trip(self, pulses: int):
        assert units_to_pulses(pulses_to_units(pulses)) == pulses


class TestBasalRateByteEncoding:
    """§8.4 / §16: rate_byte = round(abs(rate_uhr) / 0.05), clamped to [0, 100]."""

    @pytest.mark.parametrize("rate_uhr,expected_byte", [
        (0.00, 0),
        (0.05, 1),
        (0.50, 10),
        (1.00, 20),
        (2.50, 50),
        (5.00, 100),
    ])
    def test_rate_byte_value(self, rate_uhr: float, expected_byte: int):
        rates = [rate_uhr] + [0.0] * 23
        profile = encode_basal_profile(rates)
        assert profile[20] == expected_byte  # first rate byte is at offset 20

    def test_rate_above_max_clamped_to_100(self):
        rates = [999.0] + [0.0] * 23
        profile = encode_basal_profile(rates)
        assert profile[20] == 100

    def test_all_24_segments_encoded(self):
        # Verify each of the 24 hourly slots encodes independently
        rates = [float(i) * 0.05 for i in range(24)]  # 0.0, 0.05, 0.10, ...
        profile = encode_basal_profile(rates)
        rate_bytes = profile[20:]
        for i, expected in enumerate(range(24)):
            assert rate_bytes[i] == expected

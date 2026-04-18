"""Wire encode/decode pure functions for the Kaleido BLE protocol.

All functions are side-effect-free and depend only on the wire format
definitions in the technical manual (§6, §8, §13, §16).
"""

import struct
from datetime import datetime

from .constants import (
    BASAL_PROFILE_NAME,
    BASAL_PROFILE_NAME_SIZE,
    BASAL_PROFILE_SIZE,
    BASAL_RATE_MAX_BYTE,
    PULSE_TO_UNITS,
)


def encode_bolus(pulses: int) -> bytes:
    """§8.1 — 6-byte bolus request: amount (u16 LE) + 4 reserved zero bytes."""
    return struct.pack("<HHH", pulses, 0, 0)


def encode_temp_basal(pct: int, duration_min: int) -> bytes:
    """§8.2 — 4-byte temp basal request: percentage (u16 LE) + duration in minutes (u16 LE)."""
    return struct.pack("<HH", pct, duration_min)


def encode_system_time(dt: datetime, tci: int, roc: int) -> bytes:
    """§8.3 — 9-byte system time: year (u16 LE), month, day, hour, min, sec, tci, roc."""
    return struct.pack(
        "<HBBBBBBB",
        dt.year, dt.month, dt.day,
        dt.hour, dt.minute, dt.second,
        tci, roc,
    )


def decode_system_time(data: bytes) -> tuple:
    """§8.3 — Parse 9-byte system time back to (year, month, day, hour, min, sec, tci, roc)."""
    if len(data) not in (9, 113):
        raise ValueError(f"Expected 9 or 113 bytes for system time, got {len(data)}")
    return struct.unpack_from("<HBBBBBBB", data, 0)


def encode_basal_profile(rates: list[float]) -> bytes:
    """§8.4 — 44-byte basal profile: 20-byte zero-padded name + 24 hourly rate bytes.

    Each rate byte: round(abs(rate_uhr) / 0.05), clamped to [0, 100].
    """
    if len(rates) != BASAL_PROFILE_SIZE:
        raise ValueError(f"Expected {BASAL_PROFILE_SIZE} hourly rates, got {len(rates)}")
    name_bytes = BASAL_PROFILE_NAME.encode("utf-8")[:BASAL_PROFILE_NAME_SIZE]
    name_bytes = name_bytes.ljust(BASAL_PROFILE_NAME_SIZE, b"\x00")
    rate_bytes = bytes(
        min(BASAL_RATE_MAX_BYTE, round(abs(r) / PULSE_TO_UNITS)) for r in rates
    )
    return name_bytes + rate_bytes


def encode_command(cmd_id: int, payload: bytes) -> bytes:
    """§7 — Command packet: 1-byte command ID prepended to payload."""
    return bytes([cmd_id]) + payload


def encode_alarm_ack(bit_indices: list[int]) -> bytes:
    """§8.8 — 18-byte alarm acknowledgment bitfield (LSB-first, +6 bit offset).

    Each alarm's wire bit position = alarm.bitIndex + 6.
    """
    bits = bytearray(18)
    for idx in bit_indices:
        wire_bit = idx + 6
        bits[wire_bit // 8] |= 1 << (wire_bit % 8)
    return bytes(bits)


def decode_alarm_bitfield(data: bytes) -> list[int]:
    """§13 — Parse 20-byte alarm status notification into active alarm bit indices.

    Inverted logic: a bit value of 0 means the alarm is active.
    Returns list of alarm bit indices (alarm.bitIndex, without the +6 wire offset).
    """
    if len(data) != 20:
        raise ValueError(f"Expected 20 bytes for alarm bitfield, got {len(data)}")
    active = []
    for byte_idx, byte_val in enumerate(data):
        for bit_pos in range(8):
            wire_bit = byte_idx * 8 + bit_pos
            if wire_bit < 6:
                continue  # reserved header bits
            if not (byte_val >> bit_pos & 1):  # 0 = alarm active
                active.append(wire_bit - 6)
    return active


def pulses_to_units(pulses: int) -> float:
    """§16 — Convert pulse count to insulin units, rounded to 3 decimal places."""
    return round(pulses * PULSE_TO_UNITS * 1000.0) / 1000.0


def units_to_pulses(units: float) -> int:
    """§16 — Convert insulin units to pulse count (rounds to nearest pulse)."""
    return round(units / PULSE_TO_UNITS)

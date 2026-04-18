"""BLE helper utilities for Kaleido protocol tests."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Optional

from bleak import BleakClient


async def notify_and_collect(
    client: BleakClient,
    char_uuid: str,
    action: Awaitable,
    timeout: float = 5.0,
    predicate: Optional[Callable[[bytearray], bool]] = None,
) -> bytearray:
    """Subscribe to notifications on *char_uuid*, execute *action*, and return
    the first notification data that satisfies *predicate*.

    Subscription is established before *action* is awaited so no notification
    can be lost between the subscribe and trigger steps.

    Args:
        client:     A connected BleakClient.
        char_uuid:  Characteristic UUID to subscribe to.
        action:     Coroutine (already created) that triggers the notification.
        timeout:    Seconds to wait for a qualifying notification.
        predicate:  Optional filter — if None, the very first notification is
                    returned.

    Returns:
        Raw notification data as ``bytearray``.

    Raises:
        asyncio.TimeoutError: No qualifying notification arrived within *timeout*.
    """
    received: asyncio.Queue[bytearray] = asyncio.Queue()

    def _handler(_sender: object, data: bytearray) -> None:
        if predicate is None or predicate(data):
            received.put_nowait(data)

    await client.start_notify(char_uuid, _handler)
    try:
        await action
        return await asyncio.wait_for(received.get(), timeout=timeout)
    finally:
        await client.stop_notify(char_uuid)


async def read_single_byte(client: BleakClient, char_uuid: str) -> int:
    """Read a single-byte characteristic and return its integer value."""
    data = await client.read_gatt_char(char_uuid)
    return data[0]


async def read_u16_le(client: BleakClient, char_uuid: str) -> int:
    """Read a 2-byte little-endian characteristic and return its integer value."""
    import struct
    data = await client.read_gatt_char(char_uuid)
    return struct.unpack_from("<H", data)[0]

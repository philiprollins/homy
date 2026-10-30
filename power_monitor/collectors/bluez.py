"""Resolve configured devices already known to BlueZ without requiring advertising."""
import asyncio
import sys
from bleak.backends.device import BLEDevice


async def known_device(address, adapter=None):
    if sys.platform != 'linux':
        return None
    from dbus_fast import BusType, Message, MessageType
    from dbus_fast.aio import MessageBus
    bus = await asyncio.wait_for(MessageBus(bus_type=BusType.SYSTEM).connect(), 3)
    try:
        reply = await asyncio.wait_for(bus.call(Message(
            destination='org.bluez', path='/',
            interface='org.freedesktop.DBus.ObjectManager', member='GetManagedObjects')), 3)
        if reply.message_type == MessageType.ERROR:
            raise ConnectionError(f'BlueZ device lookup failed: {reply.error_name}')
        for path, interfaces in reply.body[0].items():
            if adapter and not path.startswith(f'/org/bluez/{adapter}/'):
                continue
            values = interfaces.get('org.bluez.Device1')
            if not values:
                continue
            props = {key: variant.value for key, variant in values.items()}
            if props.get('Address','').upper() == address.upper():
                return BLEDevice(address, props.get('Name') or props.get('Alias'),
                                 {'path':path, 'props':props})
        return None
    finally:
        bus.disconnect()

import asyncio
from .bluez import known_device
from ..protocols.jbd import Frames, request, decode
from bleak import BleakClient, BleakScanner
from .base import BatteryCollector


class ProtocolUnknownError(Exception):
    pass


async def discover(timeout=8):
    devices = await BleakScanner.discover(timeout=timeout, return_adv=True)
    return [(device.address, device.name or adv.local_name or '(unnamed)', adv.rssi)
            for device, adv in devices.values()]


def format_services(services):
    lines = []
    for service in services:
        lines.append(f'Service {service.uuid}: {service.description}')
        for char in service.characteristics:
            lines.append(f'  Characteristic {char.uuid}: {char.description} [{", ".join(char.properties)}]')
    return '\n'.join(lines)


class BluetoothBatteryCollector(BatteryCollector):
    def __init__(self, config, connection_lock=None):
        self.config = config
        self.connection_lock = connection_lock or asyncio.Lock()
        self.client = None
        self.parser = None
        self.queue = None
        self.subscribed = False

    async def connect(self):
        async with self.connection_lock:
            adapter = self.config.get('adapter')
            device = await known_device(self.config['address'], adapter)
            if device is None and adapter:
                device = await BleakScanner.find_device_by_address(self.config['address'], timeout=10, adapter=adapter)
                if device is None:
                    raise ConnectionError(f"Device {self.config['address']} not found on {adapter}")
            self.client = BleakClient(device or self.config['address'], timeout=15)
            await self.client.connect()

    async def read(self):
        if not self.client or not self.client.is_connected:
            raise ConnectionError('BLE device disconnected')
        notify = '0000ff01-0000-1000-8000-00805f9b34fb'
        write = '0000ff02-0000-1000-8000-00805f9b34fb'
        if not self.client.services.get_characteristic(notify) or not self.client.services.get_characteristic(write):
            raise ProtocolUnknownError('No supported JBD GATT layout; run inspect')
        if not self.subscribed:
            self.parser = Frames()
            self.queue = asyncio.Queue()
            def receive(sender, data):
                if self.parser is None or self.queue is None:
                    return
                try:
                    for frame in self.parser.feed(data):
                        self.queue.put_nowait(frame)
                except ValueError as exc:
                    self.queue.put_nowait(exc)
            await self.client.start_notify(notify, receive)
            self.subscribed = True
        # No old/unmatched response may become a new measurement.
        self.parser.buffer.clear()
        while not self.queue.empty():
            self.queue.get_nowait()
        responses = {}
        for command in (3, 4):
            await self.client.write_gatt_char(write, request(command), response=False)
            deadline = asyncio.get_running_loop().time() + 8
            while True:
                frame = await asyncio.wait_for(self.queue.get(), max(.001, deadline - asyncio.get_running_loop().time()))
                if isinstance(frame, Exception):
                    raise frame
                if frame[0] == command:
                    responses[command] = frame[1]
                    break
        return decode(self.config['id'], responses[3], responses[4])

    async def disconnect(self):
        if self.client:
            try:
                if self.client.is_connected:
                    await asyncio.wait_for(self.client.disconnect(), timeout=5)
            finally:
                self.client = None
                self.subscribed = False
                self.parser = None
                self.queue = None

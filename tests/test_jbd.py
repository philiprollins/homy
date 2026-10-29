import pytest
from power_monitor.protocols.jbd import Frames, decode, request

CAPTURE = bytes.fromhex('dd 03 00 23 14 ba fd 56 22 5f 26 ac 00 dd 32 c8 00 00 00 00 00 00 32 58 03 10 06 0b df 0b d7 0b c1 0b c0 0b bb 0b b9 f5 02 77')

def test_real_capture_fragmentation():
    parser = Frames()
    assert parser.feed(CAPTURE[:20]) == []
    assert parser.feed(CAPTURE[20:40]) == []
    frames = parser.feed(CAPTURE[40:])
    r = decode('master', frames[0][1], bytes.fromhex('0cf4')*16)
    assert r.voltage_v == 53.06
    assert r.current_a == -6.82
    assert r.soc_percent == 88
    assert r.cycles == 221
    assert r.temperatures_c[0] == 30.8
    assert r.scope == 'pack'
    assert len(r.cell_voltages_mv) == 16

def test_invalid_checksum_and_only_reads():
    bad = bytearray(CAPTURE)
    bad[5] ^= 1
    with pytest.raises(ValueError):
        Frames().feed(bad)
    with pytest.raises(ValueError):
        request(0xe1)
    assert request(3).hex() == 'dda50300fffd77'
    with pytest.raises(ValueError):
        decode('b', CAPTURE[4:-3], b'')

def test_ble_connections_are_serialized(monkeypatch):
    import asyncio
    from power_monitor.collectors import battery_ble
    active = 0
    maximum = 0
    class Client:
        def __init__(self, *args, **kwargs): pass
        async def connect(self):
            nonlocal active, maximum
            active += 1
            maximum = max(maximum, active)
            await asyncio.sleep(.001)
            active -= 1
    async def known(address): return None
    monkeypatch.setattr(battery_ble, 'known_device', known)
    monkeypatch.setattr(battery_ble, 'BleakClient', Client)
    async def run():
        lock = asyncio.Lock()
        collectors = [battery_ble.BluetoothBatteryCollector({'address':str(i)}, lock) for i in range(4)]
        await asyncio.gather(*(c.connect() for c in collectors))
    asyncio.run(run())
    assert maximum == 1

def test_known_bluez_device_is_used_without_address_scan(monkeypatch):
    import asyncio
    from power_monitor.collectors import battery_ble
    target = object()
    async def known(address):
        assert address == 'AA:C2:37:03:21:C8'
        return target
    class Client:
        def __init__(self, device, **kwargs):
            assert device is target
        async def connect(self): pass
    monkeypatch.setattr(battery_ble, 'known_device', known)
    monkeypatch.setattr(battery_ble, 'BleakClient', Client)
    asyncio.run(battery_ble.BluetoothBatteryCollector({'address':'AA:C2:37:03:21:C8'}).connect())

def test_notifications_stay_subscribed_between_polls():
    import asyncio
    from power_monitor.collectors.battery_ble import BluetoothBatteryCollector
    class Services:
        def get_characteristic(self, uuid): return True
    class Client:
        is_connected = True
        services = Services()
        subscriptions = 0
        async def start_notify(self, uuid, callback):
            self.subscriptions += 1
            self.callback = callback
        async def write_gatt_char(self, uuid, data, response):
            assert data[1] == 0xa5
            if data[2] == 3:
                self.callback(None, CAPTURE[:20])
                self.callback(None, CAPTURE[20:])
            else:
                payload = bytes.fromhex('0cf4') * 16
                body = bytes([0, len(payload)]) + payload
                frame = bytes([0xdd, 4]) + body + ((-sum(body)) & 65535).to_bytes(2,'big') + b'\x77'
                self.callback(None, frame)
        async def disconnect(self): self.is_connected = False
    async def run():
        c = BluetoothBatteryCollector({'id':'b','address':'test'})
        client = Client()
        c.client = client
        first = await c.read()
        second = await c.read()
        assert first.voltage_v == second.voltage_v == 53.06
        assert second.timestamp > first.timestamp
        assert client.subscriptions == 1
        await c.disconnect()
        assert not c.subscribed
        assert c.queue is None
    asyncio.run(run())

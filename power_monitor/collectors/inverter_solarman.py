"""SunGoldPower SPH read-only profile, verified on SGP2508150220-301638.

Register reference: https://github.com/davidrapan/ha-solarman/discussions/854
Only function 3 reads are exposed; no writes or arbitrary command API.
"""
import asyncio
from datetime import datetime, timezone
from ..models.inverter import InverterTelemetry


def decode(config, raw):
    identity = raw['identity']
    serial = ''.join(chr(word & 255) for word in identity).strip('\0 ')
    if not serial.startswith(config['expected_serial_prefix']):
        raise ValueError('Inverter serial does not match the configured device')
    battery, pv, l1, legs = raw['battery'], raw['pv'], raw['l1'], raw['legs']
    if len(identity) != 20 or len(battery) != 3 or len(pv) != 11 or len(l1) != 1 or len(legs) != 1:
        raise ValueError('Incomplete inverter response')
    return InverterTelemetry(
        inverter_id=config['id'], timestamp=datetime.now(timezone.utc), inverter_serial=serial,
        battery_voltage_v=battery[1]/10, inverter_reported_soc_percent=battery[0],
        pv1_power_w=pv[2], pv2_power_w=pv[10], load_l1_power_w=l1[0],
        load_l2_power_w=legs[0], pv1_voltage_v=pv[0]/10, pv2_voltage_v=pv[8]/10, raw_registers=raw)


class SolarmanInverterCollector:
    def __init__(self, config):
        self.config = config
        self.client = None

    async def connect(self):
        from pysolarmanv5 import PySolarmanV5Async
        self.client = PySolarmanV5Async(
            self.config['host'], self.config['logger_serial'], port=self.config.get('port',8899),
            mb_slave_id=self.config.get('slave_id',1), socket_timeout=4, auto_reconnect=False)
        await self.client.connect()

    async def read(self):
        if self.client is None:
            raise ConnectionError('Inverter not connected')
        raw = {}
        for key, start, count in [('identity',0x35,20),('battery',0x100,3),
                                  ('pv',0x107,11),('l1',0x21b,1),('legs',0x232,1),
                                  ('l1_current',0x219,1),('l2_current',0x230,1)]:
            raw[key] = await asyncio.wait_for(self.client.read_holding_registers(start,count), timeout=6)
        return decode(self.config, raw)

    async def disconnect(self):
        if self.client:
            try:
                await asyncio.wait_for(self.client.disconnect(), timeout=3)
            finally:
                self.client = None

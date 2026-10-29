import math
import time
from datetime import datetime, timezone
from .base import BatteryCollector
from ..models.telemetry import BatteryTelemetry


class MockBatteryCollector(BatteryCollector):
    def __init__(self, config):
        self.config = config
        self.connected = False

    async def connect(self):
        self.connected = True

    async def read(self):
        if not self.connected:
            raise ConnectionError('Mock disconnected')
        t = time.time() / 60
        return BatteryTelemetry(battery_id=self.config['id'], timestamp=datetime.now(timezone.utc),
            voltage_v=round(52.2 + 0.3 * math.sin(t / 20), 2), current_a=round(6 * math.sin(t / 5), 2),
            soc_percent=round(78 + 3 * math.sin(t / 30), 1), remaining_capacity_ah=round(78 + 3 * math.sin(t / 30), 1),
            full_capacity_ah=100, temperatures_c=[24.2, 25.0],
            cell_voltages_mv=[round(3262 + 5 * math.sin(t / 10 + i), 1) for i in range(16)],
            charging_enabled=True, discharging_enabled=True, cycles=120, source='mock', scope='pack')


    async def disconnect(self):
        self.connected = False

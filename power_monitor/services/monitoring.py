import asyncio
import logging
from datetime import datetime, timezone
from ..collectors.battery_ble import BluetoothBatteryCollector, ProtocolUnknownError
from ..collectors.mock_battery import MockBatteryCollector
from .energy import integrate

log = logging.getLogger(__name__)


class Monitoring:
    def __init__(self, config, database):
        self.config, self.database = config, database
        self.tasks = []
        self.ble_lock = asyncio.Lock()
        self.status = {b['id']: {'state': 'starting', 'error': None} for b in config['batteries']}

    def start(self):
        if self.tasks:
            return
        self.tasks = [asyncio.create_task(self.poll(b)) for b in self.config['batteries']]

    async def stop(self):
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks = []

    def state(self, id, state, error=None):
        if self.status[id] != {'state': state, 'error': error}:
            self.database.event(id, datetime.now(timezone.utc).isoformat(), state, error)
        self.status[id] = {'state': state, 'error': error}

    async def poll(self, battery):
        collector = MockBatteryCollector(battery) if battery['connection'] == 'mock' else BluetoothBatteryCollector(battery, self.ble_lock)
        previous = None
        connected = False
        delay = self.config['monitoring']['interval_seconds']
        backoff = delay
        try:
            while True:
                try:
                    if not connected:
                        await collector.connect()
                        connected = True
                    reading = await collector.read()
                    segments = integrate(previous, reading, self.config['monitoring']['max_gap_seconds']) if previous else []
                    if self.database.save(reading, segments):
                        previous = reading
                    self.state(battery['id'], 'connected')
                    backoff = delay
                    await asyncio.sleep(delay)
                except Exception as exc:
                    previous, connected = None, False
                    self.state(battery['id'], 'protocol_unknown' if isinstance(exc, ProtocolUnknownError) else 'disconnected', str(exc))
                    log.warning('Collector failure', extra={'battery_id': battery['id'], 'error': str(exc)})
                    try:
                        await collector.disconnect()
                    except Exception:
                        log.exception('Disconnect failed')
                    await asyncio.sleep(max(60, backoff) if isinstance(exc, ProtocolUnknownError) else backoff)
                    backoff = min(300, backoff * 2)
        finally:
            try:
                await asyncio.wait_for(collector.disconnect(), timeout=6)
            except Exception:
                log.exception('Collector shutdown disconnect failed')

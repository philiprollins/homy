import asyncio
import logging
from datetime import datetime, timezone
from ..collectors.inverter_solarman import SolarmanInverterCollector

log = logging.getLogger(__name__)


class InverterMonitoring:
    def __init__(self, config, database):
        self.config, self.database = config, database
        self.task = None
        self.status = {'state':'starting', 'error':None}

    def start(self):
        if self.task is None:
            self.task = asyncio.create_task(self.poll())

    async def stop(self):
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
            self.task = None

    def state(self, state, error=None):
        status = {'state':state, 'error':error}
        if self.status != status:
            self.database.event(self.config['id'], datetime.now(timezone.utc).isoformat(), state, error)
        self.status = status

    async def poll(self):
        collector = SolarmanInverterCollector(self.config)
        delay = self.config['interval_seconds']
        backoff = delay
        connected = False
        try:
            while True:
                try:
                    if not connected:
                        await collector.connect()
                        connected = True
                    reading = await collector.read()
                    self.database.save_inverter(reading)
                    self.state('connected')
                    backoff = delay
                    await asyncio.sleep(delay)
                except Exception as exc:
                    self.state('disconnected', str(exc))
                    log.warning('Inverter read failed', extra={'error':str(exc)})
                    connected = False
                    try:
                        await collector.disconnect()
                    except Exception:
                        log.exception('Inverter disconnect failed')
                    await asyncio.sleep(backoff)
                    backoff = min(backoff*2,300)
        finally:
            try:
                await collector.disconnect()
            except Exception:
                log.exception('Inverter shutdown cleanup failed')

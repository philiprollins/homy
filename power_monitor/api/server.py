import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone, date
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from ..storage.database import Database
from ..services.monitoring import Monitoring
from ..services.bank import summarize
from ..services.inverter import InverterMonitoring


class SPAStaticFiles(StaticFiles):
    """Serves index.html for unknown extensionless paths so client-side routes deep-link."""
    async def get_response(self, path, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as e:
            if e.status_code != 404 or path.startswith('api/') or '.' in path.rsplit('/', 1)[-1]:
                raise
            return await super().get_response('index.html', scope)


def create_app(config):
    @asynccontextmanager
    async def lifespan(app):
        db = Database(config['database']['path'])
        app.state.db = db
        app.state.monitor = Monitoring(config, db)
        app.state.monitor.start()
        inverter_config = config.get('inverter', {})
        app.state.inverter = InverterMonitoring(inverter_config, db) if inverter_config.get('enabled') else None
        if app.state.inverter:
            app.state.inverter.start()
        try:
            yield
        finally:
            if app.state.inverter:
                await app.state.inverter.stop()
            await app.state.monitor.stop()
            db.close()

    app = FastAPI(title='Local Power Monitor', lifespan=lifespan)
    batteries = {b['id']: b for b in config['batteries']}

    def check(id):
        if id not in batteries:
            raise HTTPException(404, 'Unknown battery')

    def statuses():
        result = []
        for id, b in batteries.items():
            reading = app.state.db.latest(id)
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(reading['timestamp'])).total_seconds() if reading else None
            result.append({'id': id, 'name': b['name'], 'mock': b['connection'] == 'mock',
                           **app.state.monitor.status[id], 'last_reading': reading['timestamp'] if reading else None,
                           'stale': age is None or age > config['monitoring']['max_gap_seconds']})
        return result

    def inverter_snapshot():
        monitor = app.state.inverter
        if monitor is None:
            return {'enabled':False}
        c = config['inverter']
        reading = app.state.db.latest_inverter(c['id'])
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(reading['timestamp'])).total_seconds() if reading else None
        return {'enabled':True, 'id':c['id'], 'name':c['name'], **monitor.status,
                'stale':age is None or age > c['max_gap_seconds'],
                'max_gap_seconds':c['max_gap_seconds'], 'reading':reading}

    @app.get('/api/tesla')
    async def tesla():
        """Car snapshot written by tesla_ctrl's watcher; Homy never contacts Tesla."""
        c = config.get('tesla') or {}
        if not c.get('enabled'):
            return {'enabled': False}
        try:
            snapshot = json.loads(Path(c['status_file']).read_text())
        except (OSError, ValueError) as e:
            return {'enabled': True, 'error': f'Status file unavailable: {e.__class__.__name__}', 'stale': True}
        checked = snapshot.get('checked_at')
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(checked.replace('Z', '+00:00'))).total_seconds() if checked else None
        return {'enabled': True, **snapshot, 'stale': age is None or age > c['max_age_seconds']}

    @app.get('/api/inverter')
    async def inverter():
        return inverter_snapshot()

    @app.get('/api/inverter/history')
    async def inverter_history(hours: int = Query(24,ge=1,le=720),
                               limit: int = Query(10000,ge=1,le=100000)):
        if app.state.inverter is None:
            raise HTTPException(404,'Inverter disabled')
        end = datetime.now(timezone.utc)
        start = end - timedelta(hours=hours)
        rows = app.state.db.inverter_history(config['inverter']['id'], start.isoformat(),end.isoformat(),limit+1)
        return {'readings':rows[-limit:], 'truncated':len(rows)>limit}

    @app.get('/api/bank/summary')
    async def bank_summary():
        return summarize(config['batteries'], statuses(),
                         {id: app.state.db.latest(id) for id in batteries})

    @app.get('/api/status')
    @app.get('/api/batteries')
    async def status():
        return statuses()

    @app.get('/api/system/health')
    async def health():
        app.state.db.db.execute('SELECT 1').fetchone()
        return {'database': 'ok', 'batteries': statuses(), 'inverter': inverter_snapshot(), 'timezone': 'UTC', 'max_gap_seconds': config['monitoring']['max_gap_seconds']}

    @app.get('/api/batteries/{id}/latest')
    async def latest(id: str):
        check(id)
        return app.state.db.latest(id)

    @app.get('/api/batteries/{id}/cells')
    async def cells(id: str):
        check(id)
        r = app.state.db.latest(id)
        return {k: r[k] for k in ('timestamp', 'source', 'cell_voltages_mv', 'cell_temperatures_c', 'cell_min_mv', 'cell_max_mv', 'cell_delta_mv')} if r else None

    @app.get('/api/batteries/{id}/history')
    async def history(id: str, hours: int = Query(24, ge=1, le=720), start: datetime | None = None,
                end: datetime | None = None, limit: int = Query(10000, ge=1, le=100000)):
        check(id)
        end = end or datetime.now(timezone.utc)
        start = start or end - timedelta(hours=hours)
        if start.tzinfo is None or end.tzinfo is None or start > end:
            raise HTTPException(422, 'Use timezone-aware dates in ascending order')
        rows = app.state.db.history(id, start.astimezone(timezone.utc).isoformat(), end.astimezone(timezone.utc).isoformat(), limit + 1)
        return {'readings': rows[-limit:], 'truncated': len(rows) > limit}

    def energy(battery_id, start, end, monthly):
        check(battery_id)
        end = end or datetime.now(timezone.utc).date()
        start = start or end - timedelta(days=30)
        if start > end:
            raise HTTPException(422, 'Invalid date range')
        return app.state.db.totals(battery_id, start.isoformat(), end.isoformat(), monthly)

    @app.get('/api/energy/daily')
    async def daily(battery_id: str, start: date | None = None, end: date | None = None):
        return energy(battery_id, start, end, False)

    @app.get('/api/energy/monthly')
    async def monthly(battery_id: str, start: date | None = None, end: date | None = None):
        return energy(battery_id, start, end, True)

    @app.get('/api/events')
    async def events(request: Request):
        async def stream():
            while not getattr(app.state, 'shutting_down', False) and not await request.is_disconnected():
                yield 'data: ' + json.dumps(statuses()) + '\n\n'
                await asyncio.sleep(2)
        return StreamingResponse(stream(), media_type='text/event-stream')

    app.mount('/', SPAStaticFiles(directory=Path(__file__).resolve().parents[2] / 'web', html=True), name='web')
    return app

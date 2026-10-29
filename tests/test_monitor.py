import asyncio
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from power_monitor.models.telemetry import BatteryTelemetry
from power_monitor.services.energy import integrate
from power_monitor.storage.database import Database
from power_monitor.api.server import create_app
from power_monitor.config import load_config
from power_monitor.collectors.mock_battery import MockBatteryCollector

T = datetime(2026, 1, 1, tzinfo=timezone.utc)

def reading(seconds=0, current=10):
    return BatteryTelemetry('b', T + timedelta(seconds=seconds), voltage_v=50, current_a=current)

def test_normalization():
    r = reading()
    assert r.power_w == 500
    assert reading(current=-10).power_w == -500
    assert BatteryTelemetry('b', T).power_w is None
    with pytest.raises(ValueError):
        BatteryTelemetry('b', datetime.now())
    with pytest.raises(ValueError):
        BatteryTelemetry('b', T, voltage_v=float('nan'))
    r.cell_voltages_mv = [3200, 3210]
    assert r.to_dict()['cell_delta_mv'] == 10

def test_energy():
    assert integrate(reading(), reading(3600), 3600)[0][1] == .5
    segments = integrate(reading(), reading(3600, -10), 3600)
    assert sum(s[1] for s in segments) == .125
    assert sum(s[2] for s in segments) == .125
    assert integrate(reading(), reading(31), 30) == []
    assert integrate(reading(), BatteryTelemetry('b', T + timedelta(seconds=10)), 30) == []
    assert integrate(reading(), reading(), 30) == []

def test_midnight():
    a = BatteryTelemetry('b', T - timedelta(seconds=10), voltage_v=50, current_a=10)
    rows = integrate(a, reading(10), 30)
    assert [r[0] for r in rows] == ['2025-12-31', '2026-01-01']
    assert rows[0][1] == pytest.approx(5000/3600000)

def test_database(tmp_path):
    path = str(tmp_path/'test.db')
    db = Database(path)
    assert db.save(reading(), [])
    assert db.save(reading(10), integrate(reading(), reading(10), 30))
    assert not db.save(reading(10), [('2026-01-01', 100, 100)])
    db.close()
    db = Database(path)
    assert db.latest('b')['power_w'] == 500
    assert len(db.history('b', T.isoformat(), (T+timedelta(hours=1)).isoformat())) == 2
    assert db.totals('b', '2026-01-01', '2026-01-31')[0]['charged_kwh'] < .01
    db.close()

def test_mock_disconnect():
    async def run():
        c = MockBatteryCollector({'id':'b'})
        with pytest.raises(ConnectionError):
            await c.read()
        await c.connect()
        assert (await c.read()).source == 'mock'
        await c.disconnect()
        with pytest.raises(ConnectionError):
            await c.read()
    asyncio.run(run())

def test_api(tmp_path):
    config = load_config('config.mock.yaml')
    config['database']['path'] = str(tmp_path/'api.db')
    with TestClient(create_app(config)) as client:
        import time
        for _ in range(30):
            if client.get('/api/batteries/battery-master/latest').json():
                break
            time.sleep(.01)
        assert client.get('/api/inverter').json() == {'enabled':False}
        assert client.get('/api/inverter/history').status_code == 404
        assert client.get('/').status_code == 200
        assert client.get('/api/system/health').json()['database'] == 'ok'
        assert client.get('/api/status').json()[0]['mock']
        assert client.get('/api/batteries/battery-master/latest').json()['source'] == 'mock'
        assert client.get('/api/batteries/battery-master/cells').json()['cell_voltages_mv']
        assert client.get('/api/batteries/missing/latest').status_code == 404
        assert client.get('/api/batteries/battery-master/history?start=2026-01-01T00:00:00').status_code == 422
        assert client.get('/api/energy/daily?battery_id=battery-master').status_code == 200

def test_reconnect_resets_energy(tmp_path, monkeypatch):
    from power_monitor.services import monitoring
    calls = 0
    class Failing:
        def __init__(self, config): pass
        async def connect(self): pass
        async def disconnect(self): pass
        async def read(self):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise ConnectionError('lost')
            return reading(calls)
    monkeypatch.setattr(monitoring, 'MockBatteryCollector', Failing)
    config = {'batteries':[{'id':'b','connection':'mock'}],
              'monitoring':{'interval_seconds':.001,'max_gap_seconds':30}}
    async def run():
        db = Database(str(tmp_path/'reconnect.db'))
        m = monitoring.Monitoring(config, db)
        m.start()
        m.start()
        assert len(m.tasks) == 1
        while calls < 3:
            await asyncio.sleep(.001)
        await m.stop()
        assert db.totals('b','2026-01-01','2026-01-02') == []
        db.close()
    asyncio.run(run())

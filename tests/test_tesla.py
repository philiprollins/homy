import json
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from power_monitor.config import load_config
from power_monitor.api.server import create_app


def app_config(tmp_path, status_file):
    config = load_config('config.mock.yaml')
    config['database']['path'] = str(tmp_path / 'api.db')
    config['tesla'] = {'enabled': True, 'status_file': str(status_file), 'max_age_seconds': 2700}
    return config


def test_tesla_disabled():
    config = load_config('config.mock.yaml')
    config.pop('tesla', None)
    with TestClient(create_app(config)) as client:
        assert client.get('/api/tesla').json() == {'enabled': False}


def test_tesla_snapshot_and_staleness(tmp_path):
    status_file = tmp_path / 'car_status.json'
    fresh = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    status_file.write_text(json.dumps({'checked_at': fresh, 'state': 'online', 'vehicle': {'battery_level': 67}}))
    with TestClient(create_app(app_config(tmp_path, status_file))) as client:
        body = client.get('/api/tesla').json()
        assert body['enabled'] and not body['stale'] and body['vehicle']['battery_level'] == 67
        old = (datetime.now(timezone.utc) - timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M:%SZ')
        status_file.write_text(json.dumps({'checked_at': old, 'state': 'asleep'}))
        assert client.get('/api/tesla').json()['stale']


def test_tesla_missing_file(tmp_path):
    with TestClient(create_app(app_config(tmp_path, tmp_path / 'missing.json'))) as client:
        body = client.get('/api/tesla').json()
        assert body['stale'] and 'unavailable' in body['error']

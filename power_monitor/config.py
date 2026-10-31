from pathlib import Path
import yaml


def load_config(path):
    path = Path(path).resolve()
    with path.open() as f:
        config = yaml.safe_load(f) or {}
    config.setdefault('server', {}).setdefault('host', '127.0.0.1')
    config['server'].setdefault('port', 8080)
    config.setdefault('database', {}).setdefault('path', './data/power.db')
    db = Path(config['database']['path'])
    config['database']['path'] = str(db if db.is_absolute() else path.parent / db)
    monitoring = config.setdefault('monitoring', {})
    monitoring.setdefault('interval_seconds', 10)
    monitoring.setdefault('max_gap_seconds', monitoring['interval_seconds'] * 3)
    if monitoring['interval_seconds'] < 1 or monitoring['max_gap_seconds'] <= 0:
        raise ValueError('Monitoring intervals must be positive (poll interval at least 1 second)')
    ids = set()
    for battery in config.get('batteries', []):
        if not battery.get('id') or battery['id'] in ids:
            raise ValueError('Battery IDs must be nonempty and unique')
        ids.add(battery['id'])
        if battery.get('connection') not in ('bluetooth', 'mock'):
            raise ValueError('Unsupported battery connection')
        if battery['connection'] == 'bluetooth' and not battery.get('address'):
            raise ValueError('Bluetooth battery requires an address')
        if battery.get('protocol', 'auto') != 'auto':
            raise ValueError('No BLE telemetry protocols have been verified; use auto')
    inverter = config.get('inverter')
    if inverter and inverter.get('enabled', False):
        for key in ('id','name','host','logger_serial','expected_serial_prefix'):
            if not inverter.get(key):
                raise ValueError(f'Inverter requires {key}')
        if inverter['id'] in ids:
            raise ValueError('Inverter ID must differ from battery IDs')
        inverter.setdefault('port',8899)
        inverter.setdefault('slave_id',1)
        inverter.setdefault('interval_seconds',30)
        inverter.setdefault('max_gap_seconds',inverter['interval_seconds']*3)
        if inverter['interval_seconds'] < 10 or inverter['max_gap_seconds'] <= 0:
            raise ValueError('Inverter polling must be at least 10 seconds; stale threshold must be positive')
        if not isinstance(inverter['logger_serial'], int) or not 0 < inverter['logger_serial'] < 2**32:
            raise ValueError('Logger serial must be a 32-bit positive integer')
    tesla = config.get('tesla')
    if tesla and tesla.get('enabled', False):
        if not tesla.get('status_file'):
            raise ValueError('Tesla requires status_file')
        status_file = Path(tesla['status_file'])
        tesla['status_file'] = str(status_file if status_file.is_absolute() else path.parent / status_file)
        tesla.setdefault('max_age_seconds', 2700)
    return config

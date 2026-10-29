"""Derived bank snapshot from fresh, individual pack readings only."""
def summarize(configs, statuses, readings):
    status_by_id = {s['id']: s for s in statuses}
    eligible = []
    excluded = []
    for config in configs:
        id = config['id']
        status, reading = status_by_id[id], readings.get(id)
        if status['state'] != 'connected' or status['stale'] or not reading or reading.get('scope') != 'pack':
            excluded.append(id)
        else:
            eligible.append((config, reading))
    sources = {r['source'] for _, r in eligible}
    mixed = len(sources) > 1
    if mixed:
        excluded = [c['id'] for c in configs]
        eligible = []
    powers = [r['power_w'] for _, r in eligible if r.get('power_w') is not None]
    weights = []
    temperatures = []
    alarms = []
    for config, r in eligible:
        capacity = r.get('full_capacity_ah') or config.get('capacity_ah')
        voltage = config.get('nominal_voltage')
        if r.get('soc_percent') is not None and capacity and voltage:
            weights.append((r['soc_percent'], capacity * voltage))
        temperatures.extend(r.get('temperatures_c', []) + r.get('mosfet_temperatures_c', []) + r.get('cell_temperatures_c', []))
        alarms.extend({'battery_id': config['id'], 'battery_name': config['name'], 'alarm': alarm} for alarm in r.get('alarms', []))
    power_complete = len(powers) == len(configs) and bool(configs)
    soc_complete = len(weights) == len(configs) and bool(configs)
    return {
        'configured_count': len(configs), 'reporting_count': len(eligible),
        'complete': bool(configs) and not excluded,
        'excluded_battery_ids': excluded, 'mixed_sources': mixed,
        'source': next(iter(sources)) if len(sources) == 1 else None,
        'net_power_w': sum(powers) if powers else None,
        'input_power_w': sum(max(p, 0) for p in powers) if powers else None,
        'output_power_w': sum(max(-p, 0) for p in powers) if powers else None,
        'power_complete': power_complete,
        'soc_percent': sum(s*w for s,w in weights)/sum(w for _,w in weights) if weights else None,
        'soc_complete': soc_complete,
        'soc_method': 'full_capacity_ah × configured nominal_voltage weighted',
        'temperature_min_c': min(temperatures) if temperatures else None,
        'temperature_max_c': max(temperatures) if temperatures else None,
        'temperature_reporting_count': sum(bool(r.get('temperatures_c') or r.get('mosfet_temperatures_c') or r.get('cell_temperatures_c')) for _,r in eligible),
        'alarms': alarms, 'alarm_coverage_complete': bool(configs) and not excluded,
        'oldest_reading': min((r['timestamp'] for _,r in eligible), default=None),
        'newest_reading': max((r['timestamp'] for _,r in eligible), default=None),
    }

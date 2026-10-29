from dataclasses import dataclass, asdict
from datetime import datetime
from math import isfinite


@dataclass
class InverterTelemetry:
    inverter_id: str
    timestamp: datetime
    inverter_serial: str
    battery_voltage_v: float
    inverter_reported_soc_percent: float
    pv1_power_w: float
    pv2_power_w: float
    load_l1_power_w: float
    load_l2_power_w: float
    pv1_voltage_v: float
    pv2_voltage_v: float
    raw_registers: dict
    source: str = 'hardware'

    def __post_init__(self):
        if self.timestamp.tzinfo is None:
            raise ValueError('Inverter timestamp must include timezone')
        for key in ('battery_voltage_v', 'inverter_reported_soc_percent', 'pv1_power_w',
                    'pv2_power_w', 'load_l1_power_w', 'load_l2_power_w', 'pv1_voltage_v', 'pv2_voltage_v'):
            if not isfinite(getattr(self, key)) or getattr(self, key) < 0:
                raise ValueError(f'Invalid inverter {key}')
        if self.inverter_reported_soc_percent > 100:
            raise ValueError('Invalid inverter SOC')

    def to_dict(self):
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['pv_total_power_w'] = self.pv1_power_w + self.pv2_power_w
        data['load_total_power_w'] = self.load_l1_power_w + self.load_l2_power_w
        return data

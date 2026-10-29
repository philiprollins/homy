from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from math import isfinite


@dataclass
class BatteryTelemetry:
    battery_id: str
    timestamp: datetime
    voltage_v: float | None = None
    current_a: float | None = None  # Positive means charging; negative means discharging.
    soc_percent: float | None = None
    remaining_capacity_ah: float | None = None
    full_capacity_ah: float | None = None
    temperatures_c: list[float] = field(default_factory=list)
    mosfet_temperatures_c: list[float] = field(default_factory=list)
    cell_voltages_mv: list[float] = field(default_factory=list)
    cell_temperatures_c: list[float] = field(default_factory=list)
    charging_enabled: bool | None = None
    discharging_enabled: bool | None = None
    alarms: list[str] = field(default_factory=list)
    cycles: int | None = None
    source: str = 'hardware'
    scope: str = 'unknown'

    def __post_init__(self):
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError('Timestamp must include timezone')
        self.timestamp = self.timestamp.astimezone(timezone.utc)
        for name in ('voltage_v', 'current_a', 'soc_percent', 'remaining_capacity_ah', 'full_capacity_ah'):
            value = getattr(self, name)
            if value is not None and not isfinite(value):
                raise ValueError(f'{name} must be finite')
        for name in ('temperatures_c', 'mosfet_temperatures_c', 'cell_voltages_mv', 'cell_temperatures_c'):
            if any(not isfinite(value) for value in getattr(self, name)):
                raise ValueError(f'{name} must be finite')
        if self.voltage_v is not None and self.voltage_v < 0:
            raise ValueError('Voltage cannot be negative')
        if self.soc_percent is not None and not 0 <= self.soc_percent <= 100:
            raise ValueError('SOC must be between 0 and 100')

    @property
    def power_w(self):
        return self.voltage_v * self.current_a if self.voltage_v is not None and self.current_a is not None else None

    def to_dict(self):
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['power_w'] = self.power_w
        cells = self.cell_voltages_mv
        data['cell_min_mv'] = min(cells) if cells else None
        data['cell_max_mv'] = max(cells) if cells else None
        data['cell_delta_mv'] = max(cells) - min(cells) if cells else None
        return data

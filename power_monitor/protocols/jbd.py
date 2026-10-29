"""Read-only JBD standard framing. No control/configuration opcodes."""
from datetime import datetime, timezone
from ..models.telemetry import BatteryTelemetry


def request(command):
    if command not in (3, 4):
        raise ValueError('Only basic status and cell voltage reads are permitted')
    return bytes([0xdd, 0xa5, command, 0]) + ((-command) & 0xffff).to_bytes(2, 'big') + b'\x77'


class Frames:
    def __init__(self):
        self.buffer = bytearray()

    def feed(self, data):
        self.buffer.extend(data)
        frames = []
        while self.buffer:
            if self.buffer[0] != 0xdd:
                del self.buffer[0]
                continue
            if len(self.buffer) < 4:
                break
            size = self.buffer[3] + 7
            if len(self.buffer) < size:
                break
            frame = bytes(self.buffer[:size])
            del self.buffer[:size]
            if frame[-1] != 0x77 or ((-sum(frame[2:-3])) & 65535) != int.from_bytes(frame[-3:-1], 'big'):
                raise ValueError('Invalid JBD checksum or terminator')
            if frame[2]:
                raise ValueError(f'JBD error status {frame[2]}')
            frames.append((frame[1], frame[4:-3]))
        return frames


def decode(battery_id, basic, cells):
    if len(basic) < 23 or len(basic) != 23 + basic[22] * 2:
        raise ValueError('Invalid basic status length')
    if len(cells) != basic[21] * 2 or not cells:
        raise ValueError('Cell count mismatch')
    word = lambda offset: int.from_bytes(basic[offset:offset+2], 'big')
    scale = .1 if basic[20] & 0x80 else .01
    protection = word(16)
    names = ['cell_overvoltage', 'cell_undervoltage', 'pack_overvoltage', 'pack_undervoltage',
             'charge_overtemperature', 'charge_undertemperature', 'discharge_overtemperature',
             'discharge_undertemperature', 'charge_overcurrent', 'discharge_overcurrent',
             'short_circuit', 'front_end_error', 'mosfet_lock', 'charge_timeout', 'unknown_14', 'unknown_15']
    return BatteryTelemetry(
        battery_id, datetime.now(timezone.utc), voltage_v=word(0)*.01,
        current_a=int.from_bytes(basic[2:4], 'big', signed=True)*scale,
        remaining_capacity_ah=word(4)*scale, full_capacity_ah=word(6)*scale,
        cycles=word(8), soc_percent=basic[19],
        charging_enabled=bool(basic[20]&1), discharging_enabled=bool(basic[20]&2),
        temperatures_c=[round(word(i)/10-273.1, 1) for i in range(23,len(basic),2)],
        cell_voltages_mv=[int.from_bytes(cells[i:i+2], 'big') for i in range(0,len(cells),2)],
        alarms=[name for bit,name in enumerate(names) if protection & (1<<bit)],
        source='hardware', scope='pack')

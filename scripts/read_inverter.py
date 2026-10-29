"""Read a small SunGoldPower SPH-family snapshot through SOLARMAN V5.

Reference: github.com/davidrapan/ha-solarman/discussions/854
Only Modbus function 3 (read holding registers) is used.
"""
import argparse
import json
from datetime import datetime, timezone
from pysolarmanv5 import PySolarmanV5


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', required=True)
    parser.add_argument('--logger-serial', required=True, type=int)
    parser.add_argument('--slave-id', type=int, default=1)
    args = parser.parse_args()
    client = PySolarmanV5(args.host, args.logger_serial, mb_slave_id=args.slave_id,
                         socket_timeout=5, auto_reconnect=False)
    try:
        def read(address, count):
            return client.read_holding_registers(register_addr=address, quantity=count)
        serial_words = read(0x35, 20)
        serial = ''.join(chr(word & 255) for word in serial_words).strip('\0 ')
        if not serial.startswith('SGP'):
            raise ValueError('Unrecognized inverter identity; refusing SPH field decoding')
        battery = read(0x100, 3)
        pv = read(0x107, 11)
        l1 = read(0x21b, 1)[0]
        l2 = read(0x232, 1)[0]
        print(json.dumps({
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'inverter_serial': serial,
            'profile': 'SunGoldPower SPH family; displayed fields confirmed on this inverter',
            'battery_voltage_v': battery[1] / 10,
            'inverter_reported_soc_percent': battery[0],
            'pv1_power_w': pv[2], 'pv2_power_w': pv[10],
            'load_l1_power_w': l1, 'load_l2_power_w': l2,
            'pv1_voltage_v': pv[0]/10, 'pv2_voltage_v': pv[8]/10,
            'load_total_power_w': l1 + l2,
        }, indent=2))
    finally:
        client.disconnect()


if __name__ == '__main__':
    main()

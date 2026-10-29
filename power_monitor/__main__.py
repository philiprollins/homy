import argparse
import asyncio
import json
import logging
from .config import load_config


async def diagnostic(args, config):
    from .collectors.battery_ble import discover, BluetoothBatteryCollector, format_services
    from .collectors.mock_battery import MockBatteryCollector
    if args.command == 'discover':
        for address, name, rssi in await discover():
            print(f'{address}  {rssi} dBm  {name}')
        return
    batteries = config['batteries']
    battery = next((b for b in batteries if b['id'] == args.battery), None) if args.battery else batteries[0]
    if battery is None:
        raise ValueError('Unknown battery ID')
    collector = (MockBatteryCollector if battery['connection'] == 'mock' else BluetoothBatteryCollector)(battery)
    try:
        await collector.connect()
        if args.command == 'inspect':
            if battery['connection'] == 'mock':
                print('MOCK collector: no GATT services')
            else:
                print(format_services(collector.client.services))
                print('JBD FF01/FF02 layout can be tested with monitor. Standard status reads describe the directly connected pack. No commands sent during inspection.')
        else:
            while True:
                print(json.dumps((await collector.read()).to_dict(), indent=2))
                await asyncio.sleep(config['monitoring']['interval_seconds'])
    finally:
        await collector.disconnect()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['discover', 'inspect', 'monitor', 'serve'])
    parser.add_argument('--config', default='config.example.yaml')
    parser.add_argument('--battery')
    args = parser.parse_args()
    from .logging_config import configure_logging
    configure_logging()
    config = load_config(args.config)
    try:
        if args.command == 'serve':
            from .api.runner import serve
            from .api.server import create_app
            serve(create_app(config), host=config['server']['host'], port=config['server']['port'])
        else:
            asyncio.run(diagnostic(args, config))
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        logging.error('%s', exc)
        raise SystemExit(1)


if __name__ == '__main__':
    main()

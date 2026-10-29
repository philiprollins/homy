# Homy Power Monitor

A local dashboard for ECO-WORTHY batteries and a SunGoldPower inverter. It uses Python, FastAPI, SQLite, BlueZ/BLE, and a vanilla HTML/CSS/JavaScript frontend. Telemetry stays on the local network; the app does not use a cloud service.

The included configuration describes four 51.2 V battery packs and a SunGoldPower inverter connected through a SOLARMAN Wi-Fi logger. Battery and inverter collectors use read-only telemetry commands. They do not change BMS or inverter settings.

## Requirements

- Linux with Python 3.10 or newer
- BlueZ and access to its system D-Bus service for BLE monitoring
- A Bluetooth adapter within range of the batteries
- Network access to the SOLARMAN logger for inverter monitoring

The application listens on port 8080 by default. Choose a different port if another application already uses it.

## Quick start

Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Try the dashboard with simulated battery data:

```bash
.venv/bin/python -m power_monitor serve --config config.mock.yaml
```

Open <http://127.0.0.1:8080>. Mock readings are labeled as simulated and stored in `data/mock.db`. The mock configuration does not contact the inverter.

To monitor the configured hardware:

```bash
cp config.example.yaml config.yaml
.venv/bin/python -m power_monitor serve --config config.yaml
```

Edit `config.yaml` for your installation first. It is ignored by Git. Stop the server with Ctrl+C; no separate battery shutdown command is needed. Run only one server process at a time so collectors do not compete for device connections.

## Configuration

Paths to the SQLite database are resolved relative to the configuration file. The example uses `data/power.db`; keep real and mock data in separate databases, especially when using the same battery IDs.

The example config includes:

| Device | Address or host | Interval |
| --- | --- | --- |
| Master battery | `AA:C2:37:03:21:C8` | 10 seconds |
| Battery 1 | `AA:C2:37:03:1F:6F` | 10 seconds |
| Battery 2 | `AA:C2:37:03:22:FC` | 10 seconds |
| Battery 3 | `AA:C2:37:03:23:5D` | 10 seconds |
| SOLARMAN logger | `192.168.1.236:8899` | 30 seconds |

Each configured battery is read independently over BLE. Add or remove entries under `batteries` as the installation changes; use a unique, stable ID for each pack. The labels identify the BLE devices and do not imply physical rack positions. The app does not yet query slave packs through the master's connection.

The inverter section contains the logger serial, Modbus slave ID and expected inverter serial prefix. Set `inverter.enabled: false`, or omit the section, for battery-only monitoring. Inverter polling must be at least 10 seconds.

The default `server.host: 127.0.0.1` accepts connections from the local machine. Set it to `0.0.0.0` to listen on the LAN. The API has no authentication; use a trusted network or an authenticated reverse proxy.

## Bluetooth diagnostics

On Debian or Ubuntu, install BlueZ with `sudo apt install bluez` and ensure Bluetooth is enabled. The user running the service must be allowed to access BlueZ over the system D-Bus.

```bash
.venv/bin/python -m power_monitor discover
.venv/bin/python -m power_monitor inspect --config config.yaml
.venv/bin/python -m power_monitor monitor --config config.yaml
```

Discovery lists nearby devices and RSSI where available. Inspection connects and lists GATT services and characteristic properties. Monitor prints decoded readings continuously. Use `--battery battery-1f6f`, for example, to select a pack. Stop a diagnostic before starting the server so both do not compete for the same device.

The verified batteries use JBD status and cell-voltage reads over FF01/FF02. Unknown GATT layouts are reported rather than decoded. Close the phone BMS app if it holds the connection. The collector checks BlueZ's known devices before scanning, which helps recover connections that remain known to BlueZ but have stopped advertising. It retries failures with backoff; disconnected or stale readings are labeled accordingly.

## Dashboard and measurements

The bank overview combines fresh, connected individual-pack readings:

- Charging input, discharging output, and signed net battery power.
- SOC weighted by full capacity and configured nominal voltage. Configured capacity is used when reported full capacity is unavailable.
- Reporting/configured battery count, temperature range and alarms identified by pack.

A partial-coverage warning appears when packs are missing, stale or not identified as individual packs. Mixed simulated and hardware readings are not combined. Packs are polled independently, so the bank overview is a snapshot rather than a simultaneous bank-meter measurement.

Select a pack to see voltage, current, power, SOC, capacity, temperatures, cell voltages, imbalance, cycles, alarms and history. Positive battery current and power mean charging; negative values mean discharge. Cell temperatures and MOSFET temperatures appear only when the source exposes them.

The inverter panel shows PV1/PV2 power and voltage, L1/L2 AC load current, combined output current, battery voltage and inverter-reported SOC. The current total is the sum of the two measured leg currents. Inverter SOC is separate from the battery BMS SOC. Grid input, solar/load energy totals and energy-source attribution are not implemented.

Charts offer one hour, 24 hours, seven days and 30 days. Their time labels and energy totals use UTC. The AC load history chart displays summed leg current; older readings without current registers appear as gaps.

## Sampling and storage

Battery polling defaults to 10 seconds and inverter polling to 30 seconds. The interval is a delay after each completed read, so actual spacing can be longer. Successful readings, raw inverter register responses, connection events and historical energy segments are stored in SQLite with WAL enabled.

Battery power is voltage multiplied by signed current. Charge and discharge energy are integrated between consecutive valid readings using elapsed time, with intervals split at zero crossings and UTC midnight. Missing power, disconnects, application restarts, duplicate or out-of-order timestamps, and gaps longer than `monitoring.max_gap_seconds` break integration. Energy totals describe observed intervals, not an estimate of unobserved periods.

There is no automatic retention or downsampling. Continuous operation with four batteries and the inverter was estimated at roughly 40–50 MB/day based on observed record sizes; actual growth depends on data and connectivity. Use SQLite's backup API for a live backup, or stop the service before copying the database and associated WAL files.

## API

Interactive documentation is available at <http://127.0.0.1:8080/docs>. The frontend receives live status updates using server-sent events.

| Endpoint | Purpose |
| --- | --- |
| `GET /api/status` and `/api/batteries` | Battery connection and stale status |
| `GET /api/batteries/{id}/latest` | Latest pack reading |
| `GET /api/batteries/{id}/cells` | Latest cell readings |
| `GET /api/batteries/{id}/history` | Pack history |
| `GET /api/bank/summary` | Bank snapshot and coverage |
| `GET /api/energy/daily` and `/api/energy/monthly` | Charge/discharge totals |
| `GET /api/inverter` | Inverter state and latest reading |
| `GET /api/inverter/history` | Inverter history |
| `GET /api/system/health` | Database and collector health |
| `GET /api/events` | Live battery status stream |

Battery history accepts `hours` from 1 to 720, or timezone-aware ISO `start` and `end` values. Inverter history accepts `hours` from 1 to 720. Both accept a `limit` up to 100,000 and report truncation. Energy endpoints require `battery_id` and accept optional `start` and `end` UTC dates.

## Inverter diagnostic

The standalone diagnostic uses the same local SOLARMAN logger and read-only register profile:

```bash
.venv/bin/python scripts/read_inverter.py --host 192.168.1.236 --logger-serial 3580679640
```

The installed main requirements include its dependency; `requirements-inverter.txt` is available for a diagnostic-only environment. The inverter serial prefix and displayed battery voltage, SOC, PV power and per-leg loads have been checked against this installation. Other registers and operating modes require separate verification.

## Running as a service

The example unit is [deploy/power-monitor.service](deploy/power-monitor.service). It expects the project at `/opt/power-monitor`, a dedicated `power-monitor` user, a virtual environment at `/opt/power-monitor/.venv`, and configuration at `/opt/power-monitor/config.yaml`. Give the service user read access to the application and configuration, write access to its data directory, and the required BlueZ D-Bus access. Adjust the unit's paths and user for your system.

After installing the unit under `/etc/systemd/system/`:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now power-monitor
sudo systemctl status power-monitor
sudo journalctl -u power-monitor -f
```

Stop it with `sudo systemctl stop power-monitor`. The unit restarts the service after failures.

## Tests

```bash
.venv/bin/python -m pytest -q
```

Tests cover normalization, energy integration, persistence, bank aggregation, protocol parsing, API behavior, reconnect handling and shutdown. They do not require Bluetooth hardware.

## Project layout

- `power_monitor/collectors/`: BLE, SOLARMAN and mock collectors
- `power_monitor/protocols/`: read-only JBD decoding
- `power_monitor/models/`: normalized telemetry
- `power_monitor/services/`: monitoring, bank summaries and energy calculations
- `power_monitor/storage/`: SQLite persistence
- `power_monitor/api/`: FastAPI and live updates
- `web/`: dashboard
- `tests/`: hardware-free tests
- `deploy/`: systemd example

Battery collectors share a connect/read/disconnect interface and return normalized telemetry. A future CAN collector can implement that interface; CAN communication is not currently implemented.

## Protocol references

- [JBD BLE implementation and protocol reference](https://github.com/syssi/esphome-jbd-bms)
- [ECO-WORTHY pack and slave protocol research](https://gist.github.com/dmitrych5/e2fa4ef16b0b483808e4f4089846d0d0)
- [SunGoldPower SPH register profile](https://github.com/davidrapan/ha-solarman/discussions/854)
- [SOLARMAN V5 protocol](https://github.com/jmccrohan/pysolarmanv5)
- [ECO-WORTHY manuals](https://www.eco-worthy.com/pages/manual-download)

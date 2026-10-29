# Local Power Monitor

Python 3.10+ / Linux / BlueZ. A local FastAPI dashboard with SQLite WAL history, UTC energy totals, SSE updates, multiple independent collectors, and explicit simulation mode. No cloud calls or remotely loaded frontend assets.

## Install and run

From this directory:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m power_monitor serve --config config.mock.yaml
```

Open http://127.0.0.1:8080. Mock data is labelled throughout and stored separately in data/mock.db. Stop with Ctrl+C. Run tests with `.venv/bin/python -m pytest -q`.

## Real battery discovery and inspection

Install your distribution's BlueZ package (Debian/Ubuntu: `sudo apt install bluez`) and enable Bluetooth. The service user needs permission to access the system BlueZ D-Bus service; follow the distribution's policy rather than running the application as root. Close the phone app if it occupies the battery connection.

```bash
cp config.example.yaml config.yaml
.venv/bin/python -m power_monitor discover
.venv/bin/python -m power_monitor inspect --config config.yaml
.venv/bin/python -m power_monitor monitor --config config.yaml
.venv/bin/python -m power_monitor serve --config config.yaml
```

Discovery shows advertised name, MAC and RSSI. Expected name: ECO-LFP48100-3U-0321C8; configured address: AA:C2:37:03:21:C8. Inspection lists services, characteristic UUIDs and properties. Use `--battery ID` to select a configured battery. Discovery and inspection never write characteristics. Unknown-protocol monitor exits with an actionable error; the server records protocol_unknown and retries slowly.

**Real JBD telemetry is now supported and the status response has been verified on this master.** The collector subscribes to FF01 notifications and sends only standard JBD read commands 0x03 (status) and 0x04 (cell voltages) via FF02. Fragmented responses are reassembled and checksummed; malformed/error responses are rejected. No authentication, control or configuration commands are implemented. Other GATT layouts remain unsupported.

Standard JBD reads describe the directly connected pack; they must not be presented as bank totals. The official app can access slaves, but standard addressed JBD is reported to ignore slave addresses on some ECO-WORTHY firmware. Reading slaves through one master likely requires the separate ECO-WORTHY Modbus protocol and remains unimplemented. Multiple independently configured BLE devices are supported.

Protocol research (independent implementation, no upstream code copied):
- https://github.com/syssi/esphome-jbd-bms (framing, scaling and status fields)
- https://gist.github.com/PhracturedBlue/7ef619594eaa4c27f4ff068b461865b8 (ECO-WORTHY Modbus and slave access findings)
- https://github.com/shahbaz-momi/ecoworthy-logger (existing compatible logger)

Hardware verified: AA:C2:37:03:21:C8, FF01/FF02 services, checksum-valid standard status response. The Wi-Fi address 192.168.1.65 maps to the same MAC, but a local Wi-Fi telemetry API has not been established. Slave addressing, MOSFET sensor identity, and bank summaries remain unverified.

Manufacturer background: https://www.eco-worthy.com/pages/manual-download and https://www.eco-worthy.com/pages/why-choose-eco-worthy-48v-100ah-server-rack-battery . These describe products and inter-unit communication, not a verified BLE wire specification for this unit.

## Data and energy semantics

Collectors implement connect/read/disconnect and return BatteryTelemetry. Only collectors know hardware details. A future CAN collector can use the same interface without changing storage/API/UI. CAN and grid-charger communication are not included. An optional independent SOLARMAN inverter collector is now available.

Positive current/power means energy entering the battery; negative means discharge. Power is voltage times signed current. Energy uses trapezoidal integration between consecutive valid readings, splitting zero crossings and UTC midnight. Intervals longer than max_gap_seconds, missing power, duplicate/out-of-order timestamps, errors and restarts are excluded. Energy totals therefore describe observed coverage, not guaranteed whole-day energy. No last-power extrapolation. Polling defaults to 10 seconds with capped reconnect backoff.

Raw normalized measurements, per-interval energy segments and connection/error events persist. Unique battery/timestamp prevents reconnect duplicates. Restart deliberately starts a new integration baseline. Raw history allows recalculation; no recalculation command is included. Do not switch a battery ID between mock and real sources in the same database; supplied configs use separate databases.

API documentation: /docs. History accepts hours=1/24/168/720 or timezone-aware start/end ISO timestamps, plus limit (maximum 100000). Results report truncation. Energy endpoints require battery_id and optional start/end UTC dates. Daily and monthly totals use UTC. SQLite database backup should use SQLite's backup API or stop the service before copying the database and WAL files. No automatic retention deletion.

## Deployment

Copy the project to /opt/power-monitor, create a dedicated power-monitor user, install the venv there, and copy config.example.yaml to config.yaml. Give that user read access to code/config and write access to data. Install deploy/power-monitor.service into /etc/systemd/system/, then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now power-monitor
sudo journalctl -u power-monitor -f
```

The application owns only its configured port and data directory. Run one server process (no uvicorn workers/reload) to avoid competing BLE connections. systemd restarts on failures. To allow LAN access set server.host to 0.0.0.0 and choose an unused port. The API has no authentication; use a trusted LAN or your existing authenticated reverse proxy.

## Layout

power_monitor/collectors: hardware boundary; models: normalized telemetry; services: polling/energy; storage: SQLite; api: REST/SSE; web: vanilla HTML/CSS/JS; tests: hardware-free checks; deploy: systemd unit.

## Four-pack installation

The real example configuration now includes four individually verified BLE devices:
- battery-master: AA:C2:37:03:21:C8
- battery-1f6f: AA:C2:37:03:1F:6F
- battery-22fc: AA:C2:37:03:22:FC
- battery-235d: AA:C2:37:03:23:5D

Each pack has its own BLE connection, history, energy totals and status. Select a pack using its dashboard tile or the dropdown. No registration in the phone app is required for this read-only access. Names reflect BLE addresses, not inferred physical rack positions. The master-to-slave Modbus path is documented upstream but has not been verified here; independent BLE reads are the verified operational path. No pack totals are silently treated as bank totals.

Reference for the slave-routing distinction: https://gist.github.com/dmitrych5/e2fa4ef16b0b483808e4f4089846d0d0

## Shutdown

Press Ctrl+C once, or use systemctl stop power-monitor. No BMS shutdown command is needed or sent: only the BLE connections are closed. The CLI closes live SSE streams on the shutdown signal, gives HTTP requests five seconds to drain, and bounds notification/disconnect cleanup. Avoid running duplicate server instances against the same devices. A regression test checks Ctrl+C while an SSE client remains connected.

## Bank summary

GET /api/bank/summary aggregates fresh, connected readings explicitly scoped to individual packs. The dashboard displays charging input (sum of positive power), discharging output (sum of negative power magnitudes), and signed net power. This is a snapshot of independently polled packs, not a simultaneous bank meter.

SOC is weighted by full capacity × configured nominal voltage (configured capacity is the fallback). Temperature min/max span all reported pack, MOSFET and cell sensors. Protection alarms include their originating pack. Counts and completeness flags make excluded packs and missing measurements visible. Real and mock readings are never combined. Changing the configured battery list changes the summary automatically; no four-pack count is hardcoded.

## Optional inverter read-only diagnostic

The SOLARMAN logger at 192.168.1.236 exposes local TCP 8899. A standalone diagnostic is provided; it does not change the battery collection, database or dashboard:

```bash
.venv/bin/pip install -r requirements-inverter.txt
.venv/bin/python scripts/read_inverter.py --host 192.168.1.236 --logger-serial 3580679640
```

Only Modbus read function 3 is sent. The candidate SunGoldPower SPH profile comes from https://github.com/davidrapan/ha-solarman/discussions/854 . The inverter returned an SGP2508150220-prefixed serial matching the user's device, battery voltage 52.9 V, and per-leg load values. The user confirmed the displayed snapshot on 2026-10-28: battery voltage, inverter-reported SOC, PV power and per-leg load values match the inverter/app. Other registers and operating modes remain unverified. Inverter-reported SOC is distinct from battery-BMS SOC. No control/write commands are implemented. The same verified read ranges are now available in the integrated collector described below.

## Integrated SunGoldPower inverter

The real configuration now enables the inverter dashboard and collector. Install the updated requirements before restarting. Set inverter.enabled to false to disable it; configurations without an inverter section remain battery-only. Mock configuration does not contact the inverter.

The collector uses SOLARMAN V5 over local TCP 8899 and only five fixed Modbus function-3 read ranges. Every snapshot checks expected_serial_prefix. Polling defaults to 30 seconds (minimum 10), with a 90-second stale threshold and reconnect backoff. The verified fields are PV1/PV2 power and voltage, L1/L2 AC output loads, battery voltage, and inverter-reported SOC. No settings, controls or arbitrary Modbus API are exposed.

GET /api/inverter returns connection state, stale flag and the last successful reading. GET /api/inverter/history accepts hours=1..720 and limit=1..100000 and reports truncation. Raw register responses and normalized snapshots persist in a separate inverter_readings table, indexed by inverter/time. Failed reads never manufacture a snapshot. Dashboard charts use the same time range selector as battery history.

The inverter panel is separate from the battery bank: its SOC is an inverter estimate, and its battery readings do not enter bank aggregation. Grid input is not yet read, so AC load cannot be interpreted as grid consumption. Solar/load energy totals and grid/source attribution are not implemented.

### BLE reconnect recovery

The collector resolves configured MACs through BlueZ's known Device1 objects before falling back to address-based discovery. This matters after a restart: BlueZ may retain a connection while the device stops advertising, so a new advertisement scan can incorrectly report it as absent. Known device lookup is read-only and affects only the configured device; it does not reset the adapter or disconnect other devices. Notification subscriptions now remain open for the life of each connection rather than being toggled for every poll. Responses and partial buffers are cleared before a new sample so old responses cannot become duplicate measurements.

import json
import sqlite3
from pathlib import Path


class Database:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS inverter_readings (id INTEGER PRIMARY KEY, inverter_id TEXT NOT NULL, timestamp TEXT NOT NULL, data TEXT NOT NULL, UNIQUE(inverter_id,timestamp));
        CREATE INDEX IF NOT EXISTS inverter_time ON inverter_readings(inverter_id,timestamp);
        CREATE TABLE IF NOT EXISTS readings (id INTEGER PRIMARY KEY, battery_id TEXT NOT NULL, timestamp TEXT NOT NULL, data TEXT NOT NULL, UNIQUE(battery_id,timestamp));
        CREATE INDEX IF NOT EXISTS readings_time ON readings(battery_id,timestamp);
        CREATE TABLE IF NOT EXISTS energy (reading_id INTEGER NOT NULL REFERENCES readings(id), battery_id TEXT NOT NULL, day TEXT NOT NULL, charged REAL NOT NULL, discharged REAL NOT NULL);
        CREATE INDEX IF NOT EXISTS energy_day ON energy(battery_id,day);
        CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, battery_id TEXT NOT NULL, timestamp TEXT NOT NULL, status TEXT NOT NULL, message TEXT);
        CREATE INDEX IF NOT EXISTS events_time ON events(battery_id,timestamp);
        """)
        self.db.commit()

    def save(self, reading, segments):
        data = reading.to_dict()
        with self.db:
            cursor = self.db.execute('INSERT OR IGNORE INTO readings(battery_id,timestamp,data) VALUES(?,?,?)', (reading.battery_id, data['timestamp'], json.dumps(data)))
            if not cursor.rowcount:
                return False
            self.db.executemany('INSERT INTO energy VALUES(?,?,?,?,?)', [(cursor.lastrowid, reading.battery_id, day, c, d) for day, c, d in segments])
        return True

    def event(self, battery_id, timestamp, status, message=None):
        with self.db:
            self.db.execute('INSERT INTO events(battery_id,timestamp,status,message) VALUES(?,?,?,?)', (battery_id, timestamp, status, message))

    def latest(self, battery_id):
        row = self.db.execute('SELECT data FROM readings WHERE battery_id=? ORDER BY timestamp DESC LIMIT 1', (battery_id,)).fetchone()
        return json.loads(row['data']) if row else None

    def history(self, battery_id, start, end, limit=10000):
        rows = self.db.execute('SELECT data FROM readings WHERE battery_id=? AND timestamp>=? AND timestamp<=? ORDER BY timestamp DESC LIMIT ?', (battery_id, start, end, limit)).fetchall()
        return [json.loads(r['data']) for r in reversed(rows)]

    def totals(self, battery_id, start, end, monthly=False):
        bucket = 'substr(day,1,7)' if monthly else 'day'
        rows = self.db.execute(f'SELECT {bucket} AS period, SUM(charged) AS charged_kwh, SUM(discharged) AS discharged_kwh FROM energy WHERE battery_id=? AND day>=? AND day<=? GROUP BY {bucket} ORDER BY period', (battery_id, start, end)).fetchall()
        return [dict(row) for row in rows]

    def save_inverter(self, reading):
        data = reading.to_dict()
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO inverter_readings(inverter_id,timestamp,data) VALUES(?,?,?)',
                            (reading.inverter_id, data['timestamp'], json.dumps(data)))

    def latest_inverter(self, id):
        row = self.db.execute('SELECT data FROM inverter_readings WHERE inverter_id=? ORDER BY timestamp DESC LIMIT 1', (id,)).fetchone()
        return json.loads(row['data']) if row else None

    def inverter_history(self, id, start, end, limit):
        rows = self.db.execute('SELECT data FROM inverter_readings WHERE inverter_id=? AND timestamp>=? AND timestamp<=? ORDER BY timestamp DESC LIMIT ?',
                               (id,start,end,limit)).fetchall()
        return [json.loads(row['data']) for row in reversed(rows)]

    def close(self):
        self.db.close()

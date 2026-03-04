"""
Telemetry collection module.
- Inbound: OS-level metrics (CPU, memory, disk via /proc/stat, top, etc.)
- Outbound: iDRAC power/thermal via thmtest -g s
Both push to SQLite time-series database and CSV files.
"""

import csv
import json
import os
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable

DB_PATH = None  # Set at init
CSV_DIR = None


def init_db(data_dir: str, run_id: str):
    """Initialize SQLite DB and CSV directory for a test run."""
    global DB_PATH, CSV_DIR
    run_dir = Path(data_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    DB_PATH = str(run_dir / "telemetry.db")
    CSV_DIR = str(run_dir)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS os_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        epoch REAL NOT NULL,
        phase TEXT DEFAULT '',
        cpu_pct REAL,
        mem_pct REAL,
        mem_used_mb REAL,
        mem_total_mb REAL,
        load_1m REAL,
        load_5m REAL,
        load_15m REAL,
        disk_read_kbs REAL,
        disk_write_kbs REAL,
        net_rx_kbs REAL,
        net_tx_kbs REAL,
        process_count INTEGER,
        top_processes TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS power_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        epoch REAL NOT NULL,
        phase TEXT DEFAULT '',
        sys_input_ac_w REAL,
        cpu_power_w REAL,
        dimm_power_w REAL,
        storage_power_w REAL,
        fan_power_w REAL,
        inlet_temp_c REAL,
        exhaust_temp_c REAL,
        cpu_temp_c REAL,
        raw_sensors TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS benchmark_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        epoch REAL NOT NULL,
        phase TEXT,
        event_type TEXT,
        benchmark TEXT,
        message TEXT,
        data TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS system_info (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        collected_at TEXT NOT NULL,
        source TEXT,
        key TEXT,
        value TEXT
    )""")

    conn.commit()
    conn.close()
    return run_dir


def store_os_metrics(metrics: dict):
    """Store a single OS metrics sample."""
    if not DB_PATH:
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.utcnow().isoformat() + "Z"
    epoch = time.time()
    c.execute("""INSERT INTO os_metrics
        (timestamp, epoch, phase, cpu_pct, mem_pct, mem_used_mb, mem_total_mb,
         load_1m, load_5m, load_15m, disk_read_kbs, disk_write_kbs,
         net_rx_kbs, net_tx_kbs, process_count, top_processes)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (now, epoch, metrics.get("phase", ""),
         metrics.get("cpu_pct"), metrics.get("mem_pct"),
         metrics.get("mem_used_mb"), metrics.get("mem_total_mb"),
         metrics.get("load_1m"), metrics.get("load_5m"), metrics.get("load_15m"),
         metrics.get("disk_read_kbs"), metrics.get("disk_write_kbs"),
         metrics.get("net_rx_kbs"), metrics.get("net_tx_kbs"),
         metrics.get("process_count"),
         json.dumps(metrics.get("top_processes", []))))
    conn.commit()
    conn.close()


def store_power_metrics(metrics: dict):
    """Store a single power/thermal metrics sample."""
    if not DB_PATH:
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.utcnow().isoformat() + "Z"
    epoch = time.time()
    c.execute("""INSERT INTO power_metrics
        (timestamp, epoch, phase, sys_input_ac_w, cpu_power_w, dimm_power_w,
         storage_power_w, fan_power_w, inlet_temp_c, exhaust_temp_c, cpu_temp_c,
         raw_sensors)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (now, epoch, metrics.get("phase", ""),
         metrics.get("SYS_PWR_INPUT_AC"),
         metrics.get("CPU_PWR_ALL"),
         metrics.get("DIMM_PWR_ALL"),
         metrics.get("STORAGE_PWR"),
         metrics.get("FAN_PWR_MAIN"),
         metrics.get("NODE_AMBIENT") or metrics.get("INLET_TEMP"),
         metrics.get("EXHAUST_AVG") or metrics.get("EXHAUST") or metrics.get("EXHAUST_TEMP"),
         metrics.get("CPU.1") or metrics.get("CPU_TEMP"),
         json.dumps(metrics.get("_raw", {}))))
    conn.commit()
    conn.close()


def store_benchmark_event(phase: str, event_type: str, benchmark: str,
                          message: str, data: dict = None):
    """Store a benchmark lifecycle event."""
    if not DB_PATH:
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.utcnow().isoformat() + "Z"
    epoch = time.time()
    c.execute("""INSERT INTO benchmark_events
        (timestamp, epoch, phase, event_type, benchmark, message, data)
        VALUES (?,?,?,?,?,?,?)""",
        (now, epoch, phase, event_type, benchmark, message,
         json.dumps(data) if data else None))
    conn.commit()
    conn.close()


def store_system_info(source: str, info: dict):
    """Store system info key-value pairs."""
    if not DB_PATH:
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.utcnow().isoformat() + "Z"
    for key, value in info.items():
        c.execute("""INSERT INTO system_info (collected_at, source, key, value)
            VALUES (?,?,?,?)""", (now, source, key, str(value)))
    conn.commit()
    conn.close()


def get_os_metrics(limit: int = 500) -> list:
    """Retrieve recent OS metrics."""
    if not DB_PATH:
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM os_metrics ORDER BY epoch DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return list(reversed(rows))


def get_power_metrics(limit: int = 500) -> list:
    """Retrieve recent power metrics."""
    if not DB_PATH:
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM power_metrics ORDER BY epoch DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return list(reversed(rows))


def get_benchmark_events() -> list:
    if not DB_PATH:
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM benchmark_events ORDER BY epoch ASC")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_system_info() -> dict:
    if not DB_PATH:
        return {}
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT source, key, value FROM system_info ORDER BY id ASC")
    info = {}
    for r in c.fetchall():
        src = r["source"]
        if src not in info:
            info[src] = {}
        info[src][r["key"]] = r["value"]
    conn.close()
    return info


def export_os_csv(filepath: str):
    """Export OS metrics to CSV."""
    if not DB_PATH:
        return
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM os_metrics ORDER BY epoch ASC")
    rows = c.fetchall()
    if not rows:
        conn.close()
        return
    keys = rows[0].keys()
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for r in rows:
            writer.writerow(dict(r))
    conn.close()


def export_power_csv(filepath: str):
    """Export power metrics to CSV."""
    if not DB_PATH:
        return
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM power_metrics ORDER BY epoch ASC")
    rows = c.fetchall()
    if not rows:
        conn.close()
        return
    keys = rows[0].keys()
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for r in rows:
            writer.writerow(dict(r))
    conn.close()


class InboundCollector(threading.Thread):
    """Collects OS-level metrics by running commands on the remote server."""

    def __init__(self, ssh_manager, interval: float = 2.0,
                 phase_callback: Callable = None):
        super().__init__(daemon=True)
        self.ssh = ssh_manager
        self.interval = interval
        self.phase_callback = phase_callback  # returns current phase name
        self._stop_event = threading.Event()
        self.latest: dict = {}

    def stop(self):
        self._stop_event.set()

    def run(self):
        prev_cpu = None
        prev_disk = None
        prev_net = None

        while not self._stop_event.is_set():
            try:
                phase = self.phase_callback() if self.phase_callback else ""
                metrics = {"phase": phase}

                # CPU from /proc/stat
                out, _, _ = self.ssh.os_exec(
                    "head -1 /proc/stat; sleep 0.5; head -1 /proc/stat", timeout=5)
                lines = out.strip().split("\n")
                if len(lines) >= 2:
                    cpu_pct = self._calc_cpu_pct(lines[0], lines[1])
                    metrics["cpu_pct"] = cpu_pct

                # Memory
                out, _, _ = self.ssh.os_exec(
                    "free -m | head -3", timeout=5)
                for line in out.strip().split("\n"):
                    if line.startswith("Mem:"):
                        parts = line.split()
                        if len(parts) >= 3:
                            metrics["mem_total_mb"] = float(parts[1])
                            metrics["mem_used_mb"] = float(parts[2])
                            if metrics["mem_total_mb"] > 0:
                                metrics["mem_pct"] = round(
                                    metrics["mem_used_mb"] / metrics["mem_total_mb"] * 100, 1)

                # Load average
                out, _, _ = self.ssh.os_exec("cat /proc/loadavg", timeout=5)
                parts = out.strip().split()
                if len(parts) >= 3:
                    metrics["load_1m"] = float(parts[0])
                    metrics["load_5m"] = float(parts[1])
                    metrics["load_15m"] = float(parts[2])

                # Process count
                out, _, _ = self.ssh.os_exec("ps -e --no-headers | wc -l", timeout=5)
                try:
                    metrics["process_count"] = int(out.strip())
                except:
                    pass

                # Top 5 CPU-consuming processes
                out, _, _ = self.ssh.os_exec(
                    "ps -eo pid,comm,%cpu,%mem --sort=-%cpu | head -6", timeout=5)
                top_procs = []
                for line in out.strip().split("\n")[1:]:
                    parts = line.split()
                    if len(parts) >= 4:
                        top_procs.append({
                            "pid": parts[0], "comm": parts[1],
                            "cpu": parts[2], "mem": parts[3]
                        })
                metrics["top_processes"] = top_procs

                self.latest = metrics
                store_os_metrics(metrics)

            except Exception as e:
                pass  # connection hiccup, will retry

            self._stop_event.wait(self.interval)

    @staticmethod
    def _calc_cpu_pct(line1: str, line2: str) -> float:
        """Calculate CPU% from two /proc/stat cpu lines."""
        def parse(line):
            parts = line.split()[1:]  # skip 'cpu'
            return [int(x) for x in parts]
        try:
            a = parse(line1)
            b = parse(line2)
            deltas = [b[i] - a[i] for i in range(len(a))]
            total = sum(deltas)
            idle = deltas[3] + (deltas[4] if len(deltas) > 4 else 0)
            if total > 0:
                return round((total - idle) / total * 100, 1)
        except:
            pass
        return 0.0


class OutboundCollector(threading.Thread):
    """Collects iDRAC power/thermal metrics via thmtest -g s."""

    def __init__(self, ssh_manager, interval: float = 5.0,
                 phase_callback: Callable = None):
        super().__init__(daemon=True)
        self.ssh = ssh_manager
        self.interval = interval
        self.phase_callback = phase_callback
        self._stop_event = threading.Event()
        self.latest: dict = {}

    def stop(self):
        self._stop_event.set()

    def run(self):
        while not self._stop_event.is_set():
            try:
                phase = self.phase_callback() if self.phase_callback else ""
                raw = self.ssh.get_thmtest()
                sensors = self.ssh.parse_thmtest(raw)
                sensors["phase"] = phase
                sensors["_raw"] = sensors.copy()

                self.latest = sensors
                store_power_metrics(sensors)

            except Exception as e:
                pass  # will retry

            self._stop_event.wait(self.interval)

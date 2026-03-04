"""
Persistent configuration database.
Stores server configs, test run metadata, sanity results, and run state.
Uses a single SQLite DB at data/platform.db (separate from per-run telemetry DBs).
"""

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

_lock = threading.Lock()
_DB_PATH: Optional[str] = None


def init(data_dir: str):
    """Initialize the platform-wide config database."""
    global _DB_PATH
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    _DB_PATH = str(Path(data_dir) / "platform.db")

    conn = sqlite3.connect(_DB_PATH)
    c = conn.cursor()

    # Server configurations (saved connection profiles)
    c.execute("""CREATE TABLE IF NOT EXISTS server_configs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        os_ip TEXT NOT NULL,
        os_user TEXT DEFAULT 'dell',
        os_pass TEXT DEFAULT '',
        idrac_ip TEXT DEFAULT '',
        idrac_user TEXT DEFAULT 'root',
        idrac_pass TEXT DEFAULT '',
        notes TEXT DEFAULT ''
    )""")

    # Sanity check results cached per config
    c.execute("""CREATE TABLE IF NOT EXISTS sanity_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        config_id INTEGER NOT NULL,
        checked_at TEXT NOT NULL,
        os_sysinfo TEXT,
        idrac_sysinfo TEXT,
        idrac_power TEXT,
        capabilities TEXT,
        status TEXT DEFAULT 'ok',
        FOREIGN KEY (config_id) REFERENCES server_configs(id)
    )""")

    # Test run metadata (links to per-run telemetry DBs)
    c.execute("""CREATE TABLE IF NOT EXISTS test_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL UNIQUE,
        config_id INTEGER,
        started_at TEXT NOT NULL,
        finished_at TEXT,
        status TEXT DEFAULT 'running',
        phase_duration INTEGER DEFAULT 30,
        rest_duration INTEGER DEFAULT 10,
        phases TEXT,
        total_cores INTEGER,
        fio_targets TEXT,
        current_phase TEXT DEFAULT 'idle',
        os_sysinfo TEXT,
        idrac_sysinfo TEXT,
        summary TEXT,
        notes TEXT DEFAULT '',
        FOREIGN KEY (config_id) REFERENCES server_configs(id)
    )""")

    conn.commit()
    conn.close()


def _conn():
    return sqlite3.connect(_DB_PATH)


# ─── Server Configs ──────────────────────────────────────────────────────────

def save_config(name: str, os_ip: str, os_user: str, os_pass: str,
                idrac_ip: str = "", idrac_user: str = "root",
                idrac_pass: str = "", notes: str = "") -> int:
    """Save or update a server config. Returns config id."""
    with _lock:
        conn = _conn()
        c = conn.cursor()
        now = datetime.utcnow().isoformat() + "Z"
        # Upsert
        c.execute("SELECT id FROM server_configs WHERE name = ?", (name,))
        row = c.fetchone()
        if row:
            c.execute("""UPDATE server_configs SET
                updated_at=?, os_ip=?, os_user=?, os_pass=?, idrac_ip=?,
                idrac_user=?, idrac_pass=?, notes=?
                WHERE id=?""",
                (now, os_ip, os_user, os_pass, idrac_ip,
                 idrac_user, idrac_pass, notes, row[0]))
            config_id = row[0]
        else:
            c.execute("""INSERT INTO server_configs
                (name, created_at, updated_at, os_ip, os_user, os_pass,
                 idrac_ip, idrac_user, idrac_pass, notes)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (name, now, now, os_ip, os_user, os_pass,
                 idrac_ip, idrac_user, idrac_pass, notes))
            config_id = c.lastrowid
        conn.commit()
        conn.close()
        return config_id


def list_configs() -> list:
    """Return all saved server configs."""
    conn = _conn()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""SELECT id, name, created_at, updated_at, os_ip, os_user,
        idrac_ip, idrac_user, notes FROM server_configs ORDER BY updated_at DESC""")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_config(config_id: int) -> Optional[dict]:
    """Get a single config by ID (includes passwords)."""
    conn = _conn()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM server_configs WHERE id = ?", (config_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def delete_config(config_id: int):
    with _lock:
        conn = _conn()
        conn.execute("DELETE FROM server_configs WHERE id = ?", (config_id,))
        conn.execute("DELETE FROM sanity_results WHERE config_id = ?", (config_id,))
        conn.commit()
        conn.close()


# ─── Sanity Results ──────────────────────────────────────────────────────────

def save_sanity(config_id: int, os_sysinfo: dict, idrac_sysinfo: dict,
                idrac_power: dict, capabilities: dict, status: str = "ok"):
    """Save a sanity check result for a config."""
    with _lock:
        conn = _conn()
        c = conn.cursor()
        now = datetime.utcnow().isoformat() + "Z"
        c.execute("""INSERT INTO sanity_results
            (config_id, checked_at, os_sysinfo, idrac_sysinfo, idrac_power,
             capabilities, status)
            VALUES (?,?,?,?,?,?,?)""",
            (config_id, now, json.dumps(os_sysinfo), json.dumps(idrac_sysinfo),
             json.dumps(idrac_power), json.dumps(capabilities), status))
        conn.commit()
        conn.close()


def get_latest_sanity(config_id: int) -> Optional[dict]:
    """Get the most recent sanity result for a config."""
    conn = _conn()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""SELECT * FROM sanity_results WHERE config_id = ?
        ORDER BY checked_at DESC LIMIT 1""", (config_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    for k in ("os_sysinfo", "idrac_sysinfo", "idrac_power", "capabilities"):
        if d.get(k):
            try:
                d[k] = json.loads(d[k])
            except:
                pass
    return d


# ─── Test Runs ───────────────────────────────────────────────────────────────

def create_run(run_id: str, config_id: Optional[int], phase_duration: int,
               rest_duration: int, phases: list, total_cores: int = 0,
               fio_targets: str = "", os_sysinfo: dict = None,
               idrac_sysinfo: dict = None) -> str:
    """Create a new test run record."""
    with _lock:
        conn = _conn()
        c = conn.cursor()
        now = datetime.utcnow().isoformat() + "Z"
        c.execute("""INSERT INTO test_runs
            (run_id, config_id, started_at, status, phase_duration, rest_duration,
             phases, total_cores, fio_targets, os_sysinfo, idrac_sysinfo)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (run_id, config_id, now, "running", phase_duration, rest_duration,
             json.dumps(phases), total_cores, fio_targets,
             json.dumps(os_sysinfo or {}), json.dumps(idrac_sysinfo or {})))
        conn.commit()
        conn.close()
    return run_id


def update_run_phase(run_id: str, phase: str):
    """Update the current phase of a running test."""
    with _lock:
        conn = _conn()
        conn.execute("UPDATE test_runs SET current_phase = ? WHERE run_id = ?",
                     (phase, run_id))
        conn.commit()
        conn.close()


def finish_run(run_id: str, status: str = "completed", summary: dict = None):
    """Mark a run as finished."""
    with _lock:
        conn = _conn()
        now = datetime.utcnow().isoformat() + "Z"
        conn.execute("""UPDATE test_runs SET finished_at = ?, status = ?,
            summary = ? WHERE run_id = ?""",
            (now, status, json.dumps(summary or {}), run_id))
        conn.commit()
        conn.close()


def list_runs() -> list:
    """Return all test runs with metadata."""
    conn = _conn()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""SELECT r.*, c.name as config_name
        FROM test_runs r LEFT JOIN server_configs c ON r.config_id = c.id
        ORDER BY r.started_at DESC""")
    rows = []
    for r in c.fetchall():
        d = dict(r)
        for k in ("phases", "os_sysinfo", "idrac_sysinfo", "summary"):
            if d.get(k):
                try:
                    d[k] = json.loads(d[k])
                except:
                    pass
        rows.append(d)
    conn.close()
    return rows


def get_run(run_id: str) -> Optional[dict]:
    """Get a single run by ID."""
    conn = _conn()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM test_runs WHERE run_id = ?", (run_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    for k in ("phases", "os_sysinfo", "idrac_sysinfo", "summary"):
        if d.get(k):
            try:
                d[k] = json.loads(d[k])
            except:
                pass
    return d

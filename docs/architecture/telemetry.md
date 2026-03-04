# Telemetry System Architecture

The telemetry system continuously collects performance and power data from remote servers, stores it in time-series databases, and streams it to web browsers for real-time visualization.

## Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                    Telemetry Collection Architecture                   │
│                                                                      │
│  Remote Server (OS)          Remote Server (iDRAC)                     │
│  ┌─────────────────┐        ┌─────────────────┐                        │
│  │ /proc/stat      │        │ thmtest -g s    │                        │
│  │ free -m         │        │ Power sensors   │                        │
│  │ /proc/loadavg   │        │ Thermal sensors  │                        │
│  │ ps command      │        │                 │                        │
│  └────────┬────────┘        └────────┬────────┘                        │
│           │                           │                              │
│           ▼                           ▼                              │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │              SSHManager (paramiko)                           │    │
│  │  OS exec commands    │  iDRAC interactive shell              │    │
│  └─────────────────────┼───────────────────────────────────────┘    │
│                        │                                        │    │
│  ┌─────────────────────┴───────────────────────────────────────┐    │
│  │                 Collector Threads                           │    │
│  │  InboundCollector (2s) │ OutboundCollector (5s)           │    │
│  └─────────────────────┬───────────────────────────────────────┘    │
│                        │                                        │    │
│  ┌─────────────────────┴───────────────────────────────────────┐    │
│  │              SQLite Telemetry DB                            │    │
│  │  os_metrics    │  power_metrics    │  benchmark_events   │    │
│  └─────────────────────┬───────────────────────────────────────┘    │
│                        │                                        │    │
│  ┌─────────────────────┴───────────────────────────────────────┐    │
│  │               WebSocket Broadcaster                         │    │
│  │  Broadcasts every 2s to all connected browsers             │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  Browser Clients                                                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐     │
│  │  Recharts       │  │  Metric Cards   │  │  Log Viewer     │     │
│  │  Time Series    │  │  Real-time      │  │  Live Stream    │     │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘     │
└──────────────────────────────────────────────────────────────────────┘
```

## Collector Architecture

### InboundCollector (OS Metrics)

**Purpose**: Collect operating system performance metrics every 2 seconds.

**Thread Management**:
```python
class InboundCollector(threading.Thread):
    def __init__(self, ssh_manager, interval=2.0, phase_callback=None):
        super().__init__(daemon=True)
        self.ssh = ssh_manager
        self.interval = interval
        self.phase_callback = phase_callback  # Returns current phase name
        self._stop_event = threading.Event()
        self.latest: dict = {}
```

**Metrics Collection**:

| Metric | Source | Collection Method | Frequency |
|--------|---------|------------------|----------|
| CPU % | `/proc/stat` | Delta calculation over 0.5s | Every 2s |
| Memory % | `free -m` | Parse used/total | Every 2s |
| Load Average | `/proc/loadavg` | Parse 1/5/15 min averages | Every 2s |
| Process Count | `ps -e` | Count running processes | Every 2s |
| Top Processes | `ps -eo pid,comm,%cpu,%mem` | Top 5 CPU consumers | Every 2s |
| Disk I/O | Reserved | Future implementation | Every 2s |
| Network I/O | Reserved | Future implementation | Every 2s |

**CPU Calculation Algorithm**:
```python
@staticmethod
def _calc_cpu_pct(line1: str, line2: str) -> float:
    """Calculate CPU% from two /proc/stat cpu lines."""
    def parse(line):
        parts = line.split()[1:]  # Skip 'cpu'
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
```

**Collection Loop**:
```python
def run(self):
    prev_cpu = None
    
    while not self._stop_event.is_set():
        try:
            phase = self.phase_callback() if self.phase_callback else ""
            metrics = {"phase": phase}

            # CPU from /proc/stat (two samples 0.5s apart)
            out, _, _ = self.ssh.os_exec(
                "head -1 /proc/stat; sleep 0.5; head -1 /proc/stat", timeout=5)
            lines = out.strip().split("\n")
            if len(lines) >= 2:
                cpu_pct = self._calc_cpu_pct(lines[0], lines[1])
                metrics["cpu_pct"] = cpu_pct

            # Memory from free -m
            out, _, _ = self.ssh.os_exec("free -m | head -3", timeout=5)
            for line in out.strip().split("\n"):
                if line.startswith("Mem:"):
                    parts = line.split()
                    if len(parts) >= 3:
                        metrics["mem_total_mb"] = float(parts[1])
                        metrics["mem_used_mb"] = float(parts[2])
                        if metrics["mem_total_mb"] > 0:
                            metrics["mem_pct"] = round(
                                metrics["mem_used_mb"] / metrics["mem_total_mb"] * 100, 1)

            # Store and broadcast
            self.latest = metrics
            store_os_metrics(metrics)

        except Exception as e:
            pass  # Connection hiccup, will retry

        self._stop_event.wait(self.interval)
```

### OutboundCollector (Power Metrics)

**Purpose**: Collect power and thermal data from Dell iDRAC every 5 seconds.

**Thread Management**:
```python
class OutboundCollector(threading.Thread):
    def __init__(self, ssh_manager, interval=5.0, phase_callback=None):
        super().__init__(daemon=True)
        self.ssh = ssh_manager
        self.interval = interval
        self.phase_callback = phase_callback
        self._stop_event = threading.Event()
        self.latest: dict = {}
```

**Power Sensors Collected**:

| Sensor | iDRAC Variable | Unit | Description |
|--------|----------------|------|-------------|
| SYS_PWR_INPUT_AC | SYS_PWR_INPUT_AC | Watts | Total AC input power |
| CPU Power | CPU_PWR_ALL | Watts | CPU subsystem power |
| Memory Power | DIMM_PWR_ALL | Watts | Memory subsystem power |
| Storage Power | STORAGE_PWR | Watts | Storage subsystem power |
| Fan Power | FAN_PWR_MAIN | Watts | Fan subsystem power |
| Inlet Temp | NODE_AMBIENT / INLET_TEMP | °C | Air inlet temperature |
| Exhaust Temp | EXHAUST_AVG / EXHAUST | °C | Air exhaust temperature |
| CPU Temp | CPU.1 / CPU_TEMP | °C | CPU temperature |

**Collection Loop**:
```python
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
            pass  # Will retry

        self._stop_event.wait(self.interval)
```

**iDRAC Sensor Parsing**:
```python
def parse_thmtest(self, raw: str) -> dict:
    """Parse thmtest -g s output into a dict of sensor→value.
    Handles both tabular format (space-delimited columns) and pipe-delimited format.
    """
    sensors = {}
    text = raw.replace("\r", "")

    # Check if pipe-delimited (older iDRAC firmware)
    if "|" in text and text.count("|") > 5:
        blocks = text.split("|")
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            parts = block.split()
            if len(parts) >= 2:
                try:
                    sensors[parts[0]] = float(parts[1])
                except ValueError:
                    sensors[parts[0]] = parts[1]
    else:
        # Tabular format: SENSOR_NAME  RDG  DISP  RAW  ...
        for line in text.split("\n"):
            line = line.strip()
            if not line or line.startswith("---") or line.startswith("SENSOR"):
                continue
            if line.startswith("thmtest"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                name = parts[0]
                if name in ("SENSOR_NAME", "RDG", "DISP"):
                    continue
                try:
                    val = float(parts[1])
                    sensors[name] = val
                except ValueError:
                    pass
    return sensors
```

## Database Schema

### Per-Run Telemetry Database

Each test run gets its own SQLite database at `data/<run_id>/telemetry.db`.

#### os_metrics Table

```sql
CREATE TABLE os_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,        -- ISO 8601 timestamp
    epoch REAL NOT NULL,           -- Unix epoch for time calculations
    phase TEXT DEFAULT '',          -- Current test phase
    cpu_pct REAL,                   -- CPU utilization percentage
    mem_pct REAL,                   -- Memory utilization percentage
    mem_used_mb REAL,              -- Used memory in MB
    mem_total_mb REAL,             -- Total memory in MB
    load_1m REAL,                  -- 1-minute load average
    load_5m REAL,                  -- 5-minute load average
    load_15m REAL,                 -- 15-minute load average
    disk_read_kbs REAL,            -- Disk read KB/s (reserved)
    disk_write_kbs REAL,           -- Disk write KB/s (reserved)
    net_rx_kbs REAL,               -- Network receive KB/s (reserved)
    net_tx_kbs REAL,               -- Network transmit KB/s (reserved)
    process_count INTEGER,         -- Number of running processes
    top_processes TEXT             -- JSON array of top CPU processes
);
```

#### power_metrics Table

```sql
CREATE TABLE power_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,        -- ISO 8601 timestamp
    epoch REAL NOT NULL,           -- Unix epoch
    phase TEXT DEFAULT '',          -- Current test phase
    sys_input_ac_w REAL,           -- Total AC input power (Watts)
    cpu_power_w REAL,              -- CPU subsystem power (Watts)
    dimm_power_w REAL,             -- Memory subsystem power (Watts)
    storage_power_w REAL,          -- Storage subsystem power (Watts)
    fan_power_w REAL,              -- Fan subsystem power (Watts)
    inlet_temp_c REAL,             -- Inlet air temperature (°C)
    exhaust_temp_c REAL,           -- Exhaust air temperature (°C)
    cpu_temp_c REAL,               -- CPU temperature (°C)
    raw_sensors TEXT               -- JSON of all parsed sensors
);
```

#### benchmark_events Table

```sql
CREATE TABLE benchmark_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,        -- ISO 8601 timestamp
    epoch REAL NOT NULL,           -- Unix epoch
    phase TEXT,                     -- Associated test phase
    event_type TEXT,               -- Event type (phase_start, phase_end, etc.)
    benchmark TEXT,                 -- Benchmark name (stress-ng, fio, etc.)
    message TEXT,                   -- Human-readable message
    data TEXT                      -- JSON additional data
);
```

#### system_info Table

```sql
CREATE TABLE system_info (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collected_at TEXT NOT NULL,     -- Collection timestamp
    source TEXT,                    -- 'os' or 'idrac'
    key TEXT,                       -- Information key
    value TEXT                      -- Information value
);
```

### Platform Database

Separate SQLite database at `data/platform.db` for persistent configuration:

- `server_configs` - Saved connection profiles
- `sanity_results` - Cached sanity check results  
- `test_runs` - Run metadata and history

## Data Flow Architecture

### Collection Pipeline

```
Remote Server → SSH Command → Collector Thread → SQLite DB → WebSocket → Browser
     │               │              │              │            │
     │               │              │              │            │
 /proc/stat    ssh.os_exec()   InboundCollector  store_os_metrics()  broadcast()
 free -m         (2s interval)   (2s interval)    (SQLite)          (2s)
 /proc/loadavg   →               →                →                 →
 ps command                      →                                   →
                                 →                                   →
iDRAC          ssh.idrac_exec() OutboundCollector  store_power_metrics()  broadcast()
 thmtest -g s    (5s interval)   (5s interval)    (SQLite)          (2s)
 Power sensors  →               →                →                 →
 Thermal data                   →                                   →
```

### Storage Strategy

**Time-Series Data**:
- One database per test run
- Timestamped samples with phase correlation
- Efficient querying by time range and phase
- Automatic cleanup of old runs (manual)

**Configuration Data**:
- Single platform-wide database
- Persistent across test runs
- Server configurations and run history
- Sanity check results caching

### Data Retention

```python
# Per-run data retention (manual cleanup)
def cleanup_old_runs(days_to_keep=30):
    """Remove test runs older than specified days."""
    cutoff = time.time() - (days_to_keep * 24 * 3600)
    
    for run_dir in DATA_DIR.glob("*"):
        if run_dir.is_dir() and run_dir.name.isdigit():
            db_path = run_dir / "telemetry.db"
            if db_path.exists():
                conn = sqlite3.connect(db_path)
                c = conn.cursor()
                c.execute("SELECT MIN(epoch) FROM os_metrics LIMIT 1")
                result = c.fetchone()
                if result and result[0] < cutoff:
                    shutil.rmtree(run_dir)
                    conn.close()
```

## WebSocket Broadcasting

### Message Format

```python
# Telemetry broadcast message (every 2 seconds)
{
    "type": "telemetry",
    "os": {
        "cpu_pct": 100.0,
        "mem_pct": 15.2,
        "mem_used_mb": 78643,
        "mem_total_mb": 524288,
        "load_1m": 96.0,
        "load_5m": 94.5,
        "load_15m": 88.2,
        "process_count": 285,
        "top_processes": [...]
    },
    "power": {
        "sys_input_ac_w": 450.5,
        "cpu_power_w": 120.3,
        "dimm_power_w": 45.2,
        "storage_power_w": 15.8,
        "fan_power_w": 8.5,
        "inlet_temp_c": 22.5,
        "exhaust_temp_c": 35.2,
        "cpu_temp_c": 65.0
    },
    "phase": "02_hpl_100pct",
    "running": true
}

# Log broadcast message (real-time)
{
    "type": "log",
    "line": "2026-03-02 16:30:00 [AGENT] stress-ng: info: [315587] dispatching hogs: 96 cpu"
}

# Test completion message
{
    "type": "test_complete",
    "run_id": "20260302_162939"
}
```

### Broadcasting Logic

```python
async def _ws_telemetry_loop():
    """Broadcast telemetry to all WS clients every 2s while test runs."""
    while orchestrator and orchestrator.running:
        if ws_clients:
            msg = {
                "type": "telemetry",
                "os": inbound_collector.latest if inbound_collector else {},
                "power": outbound_collector.latest if outbound_collector else {},
                "phase": orchestrator.current_phase if orchestrator else "",
                "running": orchestrator.running if orchestrator else False,
            }
            dead = []
            for ws in ws_clients:
                try:
                    await ws.send_json(msg)
                except:
                    dead.append(ws)
            for ws in dead:
                if ws in ws_clients:
                    ws_clients.remove(ws)
        await asyncio.sleep(2)
    
    # Send final "stopped" message
    if ws_clients:
        for ws in ws_clients:
            try:
                await ws.send_json({"type": "test_complete", "run_id": current_run_id})
            except:
                pass
```

## Performance Characteristics

### Collection Overhead

| Collector | Frequency | Network Overhead | CPU Overhead | Storage Overhead |
|-----------|-----------|------------------|--------------|------------------|
| Inbound | 2s | ~2KB per sample | <1% | ~200 bytes/sample |
| Outbound | 5s | ~1KB per sample | <1% | ~150 bytes/sample |

### Database Performance

**Query Examples**:
```python
# Get latest 300 OS metrics
def get_os_metrics(limit=300):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM os_metrics ORDER BY epoch DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return list(reversed(rows))

# Get phase-averaged metrics
def get_phase_averages():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT phase, AVG(cpu_pct) as avg_cpu, AVG(mem_pct) as avg_mem,
               COUNT(*) as samples
        FROM os_metrics 
        WHERE phase != '' 
        GROUP BY phase 
        ORDER BY MIN(epoch)
    """)
    return [{"phase": r[0], "avg_cpu": round(r[1], 1), 
             "avg_mem": round(r[2], 1), "samples": r[3]} 
            for r in c.fetchall()]
```

**Database Size Estimation**:
- 30-minute test @ 2s OS + 5s power intervals
- ~900 OS samples + ~360 power samples
- Database size: ~2-3 MB per run
- Indexing on `epoch` and `phase` for fast queries

### Memory Usage

**Collector Thread Memory**:
- Latest metrics dict: ~2KB
- SSH connection buffers: ~10KB
- Thread overhead: ~5KB
- Total per collector: ~20KB

**WebSocket Broadcasting**:
- Message serialization: ~5KB per broadcast
- Client connections: ~1KB per client
- Total for 10 clients: ~60KB

## Error Handling and Recovery

### Collection Failures

```python
# Network connectivity issues
try:
    out, _, _ = self.ssh.os_exec("cat /proc/stat", timeout=5)
except Exception as e:
    # Log error but continue collection
    print(f"Collection error: {e}")
    return  # Skip this sample, continue next interval

# iDRAC connectivity issues
try:
    raw = self.ssh.get_thmtest()
    sensors = self.ssh.parse_thmtest(raw)
except Exception as e:
    # Use last known values or skip
    print(f"iDRAC collection error: {e}")
    return
```

### Database Issues

```python
# Database locking
try:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    # Perform operations
    conn.commit()
except sqlite3.OperationalError as e:
    print(f"Database locked: {e}")
    # Retry or skip this sample
finally:
    conn.close()

# Database corruption detection
def verify_database():
    try:
        conn = sqlite3.connect(DB_PATH)
        result = conn.execute("PRAGMA integrity_check").fetchone()
        if result[0] != "ok":
            raise DatabaseError("Database corruption detected")
    finally:
        conn.close()
```

### WebSocket Failures

```python
# Client disconnection handling
dead = []
for ws in ws_clients:
    try:
        await ws.send_json(msg)
    except (ConnectionResetError, WebSocketDisconnect):
        dead.append(ws)
    except Exception as e:
        print(f"WebSocket error: {e}")
        dead.append(ws)

# Remove dead clients
for ws in dead:
    if ws in ws_clients:
        ws_clients.remove(ws)
```

## Data Analysis and Export

### CSV Export

```python
def export_os_csv(filepath: str):
    """Export OS metrics to CSV."""
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
```

### Statistical Analysis

```python
def generate_performance_summary():
    """Generate statistical summary of test run."""
    conn = sqlite3.connect(DB_PATH)
    
    # CPU utilization statistics
    cpu_stats = conn.execute("""
        SELECT 
            phase,
            COUNT(*) as samples,
            AVG(cpu_pct) as avg_cpu,
            MIN(cpu_pct) as min_cpu,
            MAX(cpu_pct) as max_cpu,
            stddev(cpu_pct) as std_cpu
        FROM os_metrics 
        WHERE phase != '' 
        GROUP BY phase
    """).fetchall()
    
    # Power consumption statistics
    power_stats = conn.execute("""
        SELECT 
            phase,
            COUNT(*) as samples,
            AVG(sys_input_ac_w) as avg_power,
            MIN(sys_input_ac_w) as min_power,
            MAX(sys_input_ac_w) as max_power
        FROM power_metrics 
        WHERE phase != '' 
        GROUP BY phase
    """).fetchall()
    
    return {
        "cpu_stats": [dict(row) for row in cpu_stats],
        "power_stats": [dict(row) for row in power_stats]
    }
```

---

*For the complete implementation details, see `backend/telemetry.py` in the source code.*

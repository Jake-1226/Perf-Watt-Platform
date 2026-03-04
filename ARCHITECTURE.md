# Performance Test Platform — Architecture & Documentation

**Author:** Manu Nicholas Jacob  
**Email:** ManuNicholas.Jacob@dell.com  
**Last Updated:** March 4, 2026

## Table of Contents

1. [Overview](#1-overview)
2. [System Architecture](#2-system-architecture)
3. [Directory Structure](#3-directory-structure)
4. [Backend Modules](#4-backend-modules)
5. [Frontend (UI)](#5-frontend-ui)
6. [Benchmark Agent](#6-benchmark-agent)
7. [Telemetry System](#7-telemetry-system)
8. [Database Schema](#8-database-schema)
9. [API Reference](#9-api-reference)
10. [Test Phases & Benchmarks](#10-test-phases--benchmarks)
11. [Report Generation](#11-report-generation)
12. [Deployment & Usage](#12-deployment--usage)
    - [VM Deployment Architecture](#vm-deployment-architecture)
    - [CLI Tools Architecture](#cli-tools-architecture)
13. [Known Constraints & Design Decisions](#13-known-constraints--design-decisions)

---

## 1. Overview

The **Performance Test Platform** is a full-stack benchmarking and power telemetry tool designed to stress-test Dell servers and capture correlated CPU utilization, memory usage, storage I/O, and power draw data across multiple test phases.

### Purpose

- Drive a remote server to **100% and 50% CPU utilization** using stress-ng
- Stress **all NVMe data drives in parallel** using FIO (excluding the OS drive)
- Run **combined CPU + I/O workloads** simultaneously
- Capture **real-time OS metrics** (CPU, memory, load, disk, network) via SSH
- Capture **real-time power/thermal data** from Dell iDRAC via `thmtest -g s`
- Correlate all metrics by phase and timestamp in a time-series database
- Generate **Excel reports** with charts, per-phase summaries, and raw data exports
- Provide a **live dashboard** with real-time charts and log streaming

### Key Characteristics

| Property | Value |
|---|---|
| **Runs on** | Operator's local machine (Windows/Mac/Linux) |
| **Connects to** | Remote Linux server via SSH (paramiko) |
| **Power data from** | Dell iDRAC SSH → `racadm` → `rootshell` → `thmtest -g s` |
| **Backend** | Python 3.12, FastAPI 0.115, uvicorn |
| **Frontend** | React 18 + HTM (no build step), Tailwind CSS, Recharts |
| **Database** | SQLite — one platform-wide DB + one per-run telemetry DB |
| **Benchmarks** | stress-ng (CPU), FIO (storage I/O), HPL (built but stress-ng preferred) |
| **Report format** | Excel (.xlsx) with 7 sheets + embedded charts |

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        OPERATOR'S MACHINE                           │
│                                                                     │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │              FastAPI Backend (run.py → app.py)                 │ │
│  │                                                                │ │
│  │  ┌──────────┐  ┌──────────────┐  ┌───────────────────────────┐ │ │
│  │  │ REST API │  │  WebSocket   │  │  Static File Server       │ │ │
│  │  │ /api/*   │  │  /ws         │  │  / → index.html           │ │ │
│  │  └────┬─────┘  └──────┬───────┘  └───────────────────────────┘ │ │
│  │       │               │                                        │ │
│  │  ┌────┴───────────────┴─────────────────────────────────────┐  │ │
│  │  │                    SSHManager                            │  │ │
│  │  │  OS Connection (paramiko)  │  iDRAC Connection (SSH)     │  │ │
│  │  └────────┬───────────────────┼─────────────────────────────┘  │ │
│  │           │                   │                                │ │
│  │  ┌────────┴──────┐  ┌────────┴───────────┐  ┌───────────────┐  │ │
│  │  │ Benchmark     │  │ Telemetry          │  │ Config DB     │  │ │
│  │  │ Orchestrator  │  │ InboundCollector   │  │ (platform.db) │  │ │
│  │  │               │  │ OutboundCollector  │  │               │  │ │
│  │  └───────────────┘  └───────────┬────────┘  └───────────────┘  │ │
│  │                                 │                              │ │
│  │                     ┌───────────┴────────┐                     │ │
│  │                     │ Telemetry DB       │                     │ │
│  │                     │ (per-run .db)      │                     │ │
│  │                     └────────────────────┘                     │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │              Browser (React Frontend)                          │ │
│  │  Home │ Connect │ Sanity │ Config │ Dashboard │ Report         │ │
│  │  Recharts live graphs │ WebSocket telemetry │ Log viewer       │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                    │ SSH (port 22)          │ SSH (port 22)
                    ▼                        ▼
┌───────────────────────────┐    ┌──────────────────────────┐
│     REMOTE SERVER (OS)    │    │     DELL iDRAC (BMC)     │
│     Ubuntu 24.04          │    │                          │
│                           │    │  SSH → racadm>> prompt   │
│  /tmp/bench_agent.sh      │    │  → rootshell             │
│  (deployed via SFTP)      │    │  → thmtest -g s          │
│                           │    │                          │
│  stress-ng, fio, xhpl     │    │  Power sensors:          │
│  /proc/stat, free, ps     │    │  SYS_PWR_INPUT_AC        │
│                           │    │  CPU_PWR_ALL             │
│  NVMe drives:             │    │  DIMM_PWR_ALL            │
│  nvme2n1..nvme10n1 (data) │    │  STORAGE_PWR             │
│  nvme4n1 (OS, excluded)   │    │  FAN_PWR_MAIN            │
│  nvme0n1p1, nvme1n1p1     │    │  Thermal sensors         │
│  (small, excluded)        │    │                          │
└───────────────────────────┘    └──────────────────────────┘
```

### Data Flow

1. **User** opens `http://localhost:8001` in browser
2. **Frontend** loads as a single HTML file with React/HTM (no build step)
3. User enters server credentials → **POST /api/connect** → SSHManager connects via paramiko
4. **Sanity check** collects system info, iDRAC power sample, tool availability
5. User configures test phases → **POST /api/test/start**
6. Backend deploys `bench_agent.sh` to server via SFTP
7. **BenchmarkOrchestrator** runs phases sequentially via SSH exec
8. **InboundCollector** (thread) polls OS metrics every 2s via SSH commands
9. **OutboundCollector** (thread) polls iDRAC power every 5s via `thmtest -g s`
10. Both collectors store to per-run **SQLite telemetry DB**
11. **WebSocket** broadcasts telemetry to all connected browsers every 2s
12. Frontend renders **live Recharts** graphs + metric cards + log viewer
13. On completion, **Excel report** generated with 7 sheets + charts
14. All run data persisted in `data/<run_id>/` directory

---

## 3. Directory Structure

```
perf-platform/
├── run.py                    # Entry point — starts FastAPI on configurable port
├── requirements.txt          # Python dependencies
├── ARCHITECTURE.md           # This document
│
├── backend/
│   ├── __init__.py
│   ├── app.py                # FastAPI application — REST API + WebSocket + static serving
│   ├── ssh_manager.py        # SSH connections to OS (paramiko) and iDRAC (interactive shell)
│   ├── benchmarks.py         # BenchmarkOrchestrator + BENCHMARK_AGENT_SCRIPT (shell)
│   ├── telemetry.py          # Inbound/Outbound collectors + SQLite time-series storage
│   ├── config_db.py          # Persistent platform DB — server configs, run history, sanity
│   └── reports.py            # Excel report generation (openpyxl) with 7 sheets + charts
│
├── static/
│   └── index.html            # Self-contained React frontend (HTM templates, Tailwind, Recharts)
│
├── data/                     # Created at runtime
│   ├── platform.db           # Platform-wide config DB (server_configs, sanity_results, test_runs)
│   ├── <run_id>/             # Per-run directory (e.g., 20260302_162939/)
│   │   ├── telemetry.db      # Per-run SQLite with os_metrics, power_metrics, events, sysinfo
│   │   ├── report_<run_id>.xlsx  # Generated Excel report
│   │   ├── os_metrics.csv    # Exported OS metrics
│   │   └── power_metrics.csv # Exported power metrics
│   └── ...
│
└── test_*.py                 # Test scripts (E2E, WebSocket, etc.)
```

---

## 4. Backend Modules

### 4.1 `app.py` — FastAPI Application (577 lines)

The main application server. Responsibilities:

- **Static file serving**: Serves `index.html` at `/` and static assets
- **Config CRUD**: Save/load/delete server connection profiles
- **Connection management**: Connect/disconnect to OS (SSH) and iDRAC (SSH→racadm→rootshell)
- **Sanity check**: Collect system info, verify tool availability, sample power data
- **Test execution**: Deploy benchmark agent, start/stop test sequences, stream logs
- **Telemetry endpoints**: Serve OS metrics, power metrics, latest readings, events
- **Report generation**: Generate Excel report, export CSVs, provide download
- **Run history**: List past runs with file-based fallback for pre-DB runs
- **WebSocket**: Broadcast live telemetry and log lines to all connected browsers

Key design:
- Uses `ThreadPoolExecutor` for blocking SSH calls so the async event loop isn't blocked
- WebSocket telemetry loop runs as an asyncio task, broadcasting every 2s while test runs
- Log lines are broadcast to WebSocket clients via thread-safe `call_soon_threadsafe`

### 4.2 `ssh_manager.py` — SSH Connection Manager (323 lines)

Manages two independent SSH connections:

**OS Connection** (standard paramiko SSH):
- `connect_os(ip, user, password)` → persistent `SSHClient`
- `os_exec(cmd, timeout)` → execute command, return (stdout, stderr, exit_code)
- `os_exec_stream(cmd, callback)` → stream stdout line-by-line with PTY
- `sftp_put/get/get_bytes` → file transfer operations
- `get_os_sysinfo()` → 16 system info commands (hostname, CPU, memory, disks, BIOS, etc.)

**iDRAC Connection** (interactive shell navigation):
- `connect_idrac(ip, user, password)` → SSH → wait for `racadm>>` prompt → send `rootshell` → wait for `#` prompt
- `idrac_exec(cmd)` → send command to rootshell, read until prompt
- `get_thmtest()` → run `thmtest -g s` on iDRAC rootshell
- `parse_thmtest(raw)` → parse pipe-delimited or tabular sensor output into dict
- `get_idrac_sysinfo()` → collect iDRAC version, service tag, BIOS version

### 4.3 `benchmarks.py` — Benchmark Orchestrator (619 lines)

Two components:

**1. BENCHMARK_AGENT_SCRIPT (350 lines of Bash)**
A shell script deployed to `/tmp/bench_agent.sh` on the remote server. Actions:

| Action | Description |
|---|---|
| `install_deps` | apt-get install build-essential, gfortran, OpenMPI, FIO, stress-ng, bc, etc. |
| `setup_hpl` | Download HPL 2.3, configure with OpenBLAS + OpenMPI, build, fix ownership |
| `run_hpl` | Run multiple parallel xhpl instances pinned to core groups via taskset |
| `run_fio` | Generate FIO config for all target dirs, run randrw workload |
| `run_stress_ng` | Run stress-ng with specified cores and stressor type |
| `sysinfo` | Dump comprehensive system info |

Key design decisions in the agent:
- **`do_sudo()`**: Uses `SUDO_PASS` env var with `sudo -S` for non-root users
- **HPL**: Built from source with auto-detected MPI paths and OpenBLAS. Runs multiple parallel `./xhpl` instances with `taskset` CPU pinning (avoids `mpirun` which segfaults due to vendor/system MPI version mismatch)
- **FIO**: Validates target directories, generates a `.fio` config file with one job per drive, uses `libaio` direct I/O with configurable iodepth (64 for 100%, 8 for 50%)
- **stress-ng**: Falls back to `yes > /dev/null` if stress-ng not available

**2. BenchmarkOrchestrator (Python class)**

| Method | Description |
|---|---|
| `deploy_agent()` | SFTP upload `bench_agent.sh` to `/tmp/` |
| `install_deps()` | Run `install_deps` action on server |
| `setup_hpl()` | Build HPL on server |
| `run_test_sequence(config)` | Execute all phases in background thread |
| `stop()` | Set stop event, kill running benchmarks on server |
| `_run_benchmark(cmd, duration, phase)` | Run single benchmark with streaming output |
| `_run_parallel(cmds, duration, phase)` | Run multiple benchmarks simultaneously via `nohup bash -c` |

### 4.4 `telemetry.py` — Telemetry Collection (406 lines)

**InboundCollector** (daemon thread, 2s interval):
Polls OS metrics via SSH commands:
- CPU% from two `/proc/stat` reads 0.5s apart (delta-based calculation)
- Memory from `free -m`
- Load average from `/proc/loadavg`
- Process count from `ps -e`
- Top 5 CPU-consuming processes from `ps -eo`

**OutboundCollector** (daemon thread, 5s interval):
Polls iDRAC power/thermal via `thmtest -g s`:
- SYS_PWR_INPUT_AC (total AC input power)
- CPU_PWR_ALL (CPU subsystem power)
- DIMM_PWR_ALL (memory power)
- STORAGE_PWR (storage subsystem power)
- FAN_PWR_MAIN (fan power)
- Thermal sensors (inlet, exhaust, CPU temperatures)

Both collectors store every sample to the per-run SQLite telemetry DB and expose a `.latest` dict for real-time WebSocket broadcast.

### 4.5 `config_db.py` — Persistent Configuration Database (275 lines)

Platform-wide SQLite database (`data/platform.db`) with three tables:

- **server_configs**: Saved connection profiles (name, IPs, credentials, notes)
- **sanity_results**: Cached sanity check results per config (sysinfo, capabilities, power sample)
- **test_runs**: Run metadata (run_id, config_id, phases, status, summary, timestamps)

Supports upsert for configs, run lifecycle (create → update phase → finish), and full history queries with JSON field deserialization.

### 4.6 `reports.py` — Excel Report Generator (443 lines)

Generates a professional Excel workbook with 7 sheets:

| Sheet | Contents |
|---|---|
| **Summary** | System info, per-phase stats table, overall duration/power stats |
| **OS Metrics** | Raw time-series: timestamp, cpu_pct, mem_pct, load, disk I/O, net I/O |
| **Power Metrics** | Raw time-series: AC power, CPU power, DIMM, storage, fan, temperatures |
| **Phase Summary** | Aggregated per-phase: avg/min/max CPU%, avg/min/max AC power, per-subsystem power |
| **System Info** | All collected system info key-value pairs |
| **Benchmark Events** | Phase start/end events with timestamps |
| **Charts** | 4 embedded charts: CPU%, Memory%, AC Power, CPU Power over time |

Also provides `generate_summary()` for JSON dashboard summaries.

---

## 5. Frontend (UI)

Single-file React application using **HTM** (tagged template literals, no Babel/JSX build step), **Tailwind CSS** (CDN), and **Recharts** (UMD) for charts.

### Technology Stack

| Library | Version | Purpose |
|---|---|---|
| React | 18 (development) | UI framework |
| ReactDOM | 18 | DOM rendering |
| HTM | 3 | JSX-like syntax without build step |
| Tailwind CSS | CDN | Utility-first CSS |
| Recharts | 2.13.3 | Charts (AreaChart, LineChart) |
| PropTypes | 15 | Required by Recharts |
| Inter + JetBrains Mono | Google Fonts | Typography |

### UI Panels (Tab-based navigation)

| Tab | Component | Description |
|---|---|---|
| **Home** | `HomePanel` | Landing page with saved server configs grid + recent runs table. Quick-connect and new config buttons. |
| **Connect** | `ConnectPanel` | Form for OS IP/user/password + iDRAC IP/user/password. Connect button with loading state. Toast notifications for success/error. |
| **Sanity** | `SanityPanel` | Auto-runs on navigation. Displays OS sysinfo (hostname, CPU, memory, disks), iDRAC power sample, and tool capability checks (gcc, fio, stress-ng, etc.). |
| **Config** | `ConfigPanel` | Test configuration: phase duration, rest duration. Phase list with add/remove. Saved config dropdown. Start test button. |
| **Dashboard** | `DashboardPanel` | Live monitoring: 6 metric cards (CPU%, Mem%, AC Power, CPU Power, Storage Power, Fan Power), 2 Recharts time-series graphs (CPU/Mem, Power), live log viewer with auto-scroll. Stop test and generate report buttons. |
| **Report** | `ReportPanel` | Test summary display, download report button, past runs browser. |

### Error Handling

- **ErrorBoundary** class wraps the entire App to prevent blank-page crashes
- **Toast notifications** (`showMsg`) replace `alert()` for user feedback
- **React development mode** enabled for detailed error messages in console
- All `style` props use React object syntax (`style=${{key: 'value'}}`) instead of CSS strings

---

## 6. Benchmark Agent

The benchmark agent (`bench_agent.sh`) is a self-contained Bash script deployed to the remote server via SFTP. It handles all benchmark execution locally on the server, controlled by the Python orchestrator over SSH.

### Agent Deployment Flow

```
Operator Machine                    Remote Server
─────────────────                   ─────────────
1. SFTP upload bench_agent.sh  ──→  /tmp/bench_agent.sh
2. chmod +x                    ──→  (executable)
3. SSH exec: SUDO_PASS='...'   ──→  bash /tmp/bench_agent.sh install_deps
   bash /tmp/bench_agent.sh
   <action> <args>
```

### FIO Storage Benchmarking

FIO target discovery at test start:
```bash
df -BG /mnt/nvme* 2>/dev/null | awk 'NR>1 && $4+0>=2 {print $6}' | sort
```

This finds all `/mnt/nvme*` mountpoints with at least 2GB free space. On the reference server:

| Drive | Size | Mount | Included | Notes |
|---|---|---|---|---|
| nvme4n1 | 894G | /, /boot | **Excluded** | OS drive (LVM, not under /mnt) |
| nvme0n1p1 | 1G | /mnt/nvme0n1p1 | **Excluded** | < 2GB free |
| nvme1n1p1 | 94M | /mnt/nvme1n1p1 | **Excluded** | < 2GB free |
| nvme2n1 | 3.5T | /mnt/nvme2n1 | **Included** | Data drive |
| nvme3n1 | 3.5T | /mnt/nvme3n1 | **Included** | Data drive |
| nvme5n1 | 3.5T | /mnt/nvme5n1 | **Included** | Data drive |
| nvme6n1 | 3.5T | /mnt/nvme6n1 | **Included** | Data drive |
| nvme7n1 | 3.5T | /mnt/nvme7n1 | **Included** | Data drive |
| nvme8n1 | 3.5T | /mnt/nvme8n1 | **Included** | Data drive |
| nvme9n1 | 3.5T | /mnt/nvme9n1 | **Included** | Data drive |
| nvme10n1 | 3.5T | /mnt/nvme10n1 | **Included** | Data drive |

**Result: 8 data drives stressed in parallel**

FIO configuration per drive:
- `ioengine=libaio` (async I/O)
- `direct=1` (bypass page cache)
- `rw=randrw` (random read/write)
- `rwmixread=50` (50/50 read/write)
- `bs=128k` (block size)
- 100% load: `iodepth=64`, `size=256M`
- 50% load: `iodepth=8`, `size=128M`

### CPU Stress (stress-ng)

HPL phases (`hpl_100`, `hpl_50`) actually use `stress-ng --cpu` for reliable CPU loading:

- **100% CPU**: `stress-ng --cpu 96 --timeout 30s` → dispatches 96 CPU workers (one per core)
- **50% CPU**: `stress-ng --cpu 48 --timeout 30s` → dispatches 48 CPU workers (half of cores)

This was chosen over HPL because:
1. `mpirun ./xhpl` segfaults due to vendor/system OpenMPI version mismatch on the reference server
2. Direct `./xhpl` without MPI doesn't effectively use multiple cores
3. `stress-ng` reliably achieves exact target CPU utilization

### HPL (retained for optional use)

HPL 2.3 is still built and available. The `run_hpl` action:
- Downloads and compiles HPL with OpenBLAS and system MPI
- Runs multiple parallel `./xhpl` instances with CPU pinning via `taskset`
- Uses `OPENBLAS_NUM_THREADS` for multi-threaded BLAS per instance
- Calculates matrix size N from 60% of available memory (up to N=80000)
- Fixes ownership after build to prevent permission issues

### Parallel Execution (hpl_fio phases)

Combined phases run stress-ng and FIO simultaneously:
```bash
nohup bash -c "SUDO_PASS='...' bash /tmp/bench_agent.sh run_stress_ng 96 30 cpu" > /tmp/bench_par_0.log 2>&1 &
nohup bash -c "SUDO_PASS='...' bash /tmp/bench_agent.sh run_fio 100 30 '/mnt/nvme...'" > /tmp/bench_par_1.log 2>&1 &
```

The orchestrator waits for the phase duration, then kills both jobs and collects output logs.

---

## 7. Telemetry System

### Collection Architecture

```
                 SSH exec commands              iDRAC interactive shell
                 (every 2 seconds)              (every 5 seconds)
                      │                              │
          ┌───────────┴───────────┐      ┌───────────┴───────────┐
          │  InboundCollector     │      │  OutboundCollector     │
          │  (daemon thread)      │      │  (daemon thread)       │
          │                       │      │                        │
          │  /proc/stat → CPU%   │      │  thmtest -g s:         │
          │  free -m → Memory    │      │  SYS_PWR_INPUT_AC      │
          │  /proc/loadavg       │      │  CPU_PWR_ALL            │
          │  ps → processes      │      │  DIMM_PWR_ALL           │
          └───────────┬───────────┘      │  STORAGE_PWR            │
                      │                  │  FAN_PWR_MAIN           │
                      │                  │  Thermal sensors        │
                      │                  └───────────┬─────────────┘
                      │                              │
                      ▼                              ▼
              ┌───────────────────────────────────────────┐
              │         SQLite Telemetry DB               │
              │         (per-run, data/<run_id>/)          │
              │                                           │
              │  os_metrics    │  power_metrics            │
              │  benchmark_events │  system_info           │
              └────────────────────┬──────────────────────┘
                                   │
                      ┌────────────┴────────────┐
                      │  WebSocket Broadcaster   │
                      │  (asyncio task, 2s)      │
                      └────────────┬─────────────┘
                                   │
                      ┌────────────┴────────────┐
                      │  Browser (Recharts)      │
                      │  Live graphs + metrics   │
                      └──────────────────────────┘
```

### OS Metrics Collected (per sample)

| Metric | Source | Type |
|---|---|---|
| `cpu_pct` | `/proc/stat` delta over 0.5s | % (0–100) |
| `mem_pct` | `free -m` | % (0–100) |
| `mem_used_mb` | `free -m` | MB |
| `mem_total_mb` | `free -m` | MB |
| `load_1m/5m/15m` | `/proc/loadavg` | float |
| `disk_read_kbs` | reserved | KB/s |
| `disk_write_kbs` | reserved | KB/s |
| `net_rx_kbs` | reserved | KB/s |
| `net_tx_kbs` | reserved | KB/s |
| `process_count` | `ps -e --no-headers \| wc -l` | int |
| `top_processes` | `ps -eo pid,comm,%cpu,%mem` | JSON array |

### Power Metrics Collected (per sample)

| Metric | iDRAC Sensor | Unit |
|---|---|---|
| `sys_input_ac_w` | SYS_PWR_INPUT_AC | Watts |
| `cpu_power_w` | CPU_PWR_ALL | Watts |
| `dimm_power_w` | DIMM_PWR_ALL | Watts |
| `storage_power_w` | STORAGE_PWR | Watts |
| `fan_power_w` | FAN_PWR_MAIN | Watts |
| `inlet_temp_c` | NODE_AMBIENT / INLET_TEMP | °C |
| `exhaust_temp_c` | EXHAUST_AVG / EXHAUST | °C |
| `cpu_temp_c` | CPU.1 / CPU_TEMP | °C |

---

## 8. Database Schema

### Platform Database (`data/platform.db`)

```sql
-- Saved server connection profiles
CREATE TABLE server_configs (
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
);

-- Cached sanity check results per config
CREATE TABLE sanity_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_id INTEGER NOT NULL REFERENCES server_configs(id),
    checked_at TEXT NOT NULL,
    os_sysinfo TEXT,        -- JSON
    idrac_sysinfo TEXT,     -- JSON
    idrac_power TEXT,       -- JSON
    capabilities TEXT,      -- JSON
    status TEXT DEFAULT 'ok'
);

-- Test run metadata
CREATE TABLE test_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL UNIQUE,
    config_id INTEGER REFERENCES server_configs(id),
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT DEFAULT 'running',
    phase_duration INTEGER DEFAULT 30,
    rest_duration INTEGER DEFAULT 10,
    phases TEXT,             -- JSON array
    total_cores INTEGER,
    fio_targets TEXT,
    current_phase TEXT DEFAULT 'idle',
    os_sysinfo TEXT,         -- JSON
    idrac_sysinfo TEXT,      -- JSON
    summary TEXT,            -- JSON
    notes TEXT DEFAULT ''
);
```

### Per-Run Telemetry Database (`data/<run_id>/telemetry.db`)

```sql
CREATE TABLE os_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    epoch REAL NOT NULL,
    phase TEXT DEFAULT '',
    cpu_pct REAL,
    mem_pct REAL,
    mem_used_mb REAL,
    mem_total_mb REAL,
    load_1m REAL, load_5m REAL, load_15m REAL,
    disk_read_kbs REAL, disk_write_kbs REAL,
    net_rx_kbs REAL, net_tx_kbs REAL,
    process_count INTEGER,
    top_processes TEXT           -- JSON array
);

CREATE TABLE power_metrics (
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
    raw_sensors TEXT             -- JSON dict
);

CREATE TABLE benchmark_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    epoch REAL NOT NULL,
    phase TEXT,
    event_type TEXT,             -- 'phase_start', 'phase_end', 'sequence_start', 'sequence_end'
    benchmark TEXT,
    message TEXT,
    data TEXT                    -- JSON
);

CREATE TABLE system_info (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collected_at TEXT NOT NULL,
    source TEXT,                 -- 'os' or 'idrac'
    key TEXT,
    value TEXT
);
```

---

## 9. API Reference

### Configuration Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/configs` | List all saved server configurations |
| POST | `/api/configs` | Save a new server configuration |
| GET | `/api/configs/{id}` | Get config by ID (includes passwords) |
| DELETE | `/api/configs/{id}` | Delete a config and its sanity results |
| GET | `/api/configs/{id}/sanity` | Get latest sanity result for a config |

### Connection Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/connect` | Connect to server OS + iDRAC. Body: `ConnectRequest` |
| POST | `/api/disconnect` | Disconnect all SSH connections, stop collectors |
| GET | `/api/connection_status` | Returns `{os_connected, idrac_connected}` |

### Sanity Check

| Method | Path | Description |
|---|---|---|
| POST | `/api/sanity_check?config_id=X` | Run full sanity check (OS sysinfo, iDRAC power, tool caps) |

### Test Execution

| Method | Path | Description |
|---|---|---|
| POST | `/api/test/start` | Start test run. Body: `TestConfig` |
| POST | `/api/test/stop` | Stop running test, kill server-side processes |
| GET | `/api/test/status` | Current status: running, phase, run_id, log count |
| GET | `/api/test/logs?offset=0&limit=200` | Paginated benchmark logs |

### Telemetry

| Method | Path | Description |
|---|---|---|
| GET | `/api/telemetry/os?limit=300` | OS metrics time-series |
| GET | `/api/telemetry/power?limit=300` | Power metrics time-series |
| GET | `/api/telemetry/latest` | Latest OS + power readings |
| GET | `/api/telemetry/events` | Benchmark lifecycle events |
| GET | `/api/telemetry/sysinfo` | Collected system info dict |

### Reports

| Method | Path | Description |
|---|---|---|
| POST | `/api/report/generate` | Generate Excel report + CSV exports |
| GET | `/api/report/download/{run_id}` | Download Excel report file |
| GET | `/api/report/summary` | JSON summary of current run |

### Run History

| Method | Path | Description |
|---|---|---|
| GET | `/api/runs` | List all test runs (DB + filesystem fallback) |
| GET | `/api/runs/{run_id}` | Get detailed run info |

### WebSocket

| Path | Description |
|---|---|
| `/ws` | Real-time telemetry + log streaming. Messages: `{type: "telemetry", os, power, phase, running}`, `{type: "log", line}`, `{type: "test_complete", run_id}` |

---

## 10. Test Phases & Benchmarks

### Default 8-Phase Test Sequence

| # | Phase Name | Type | What Happens |
|---|---|---|---|
| 1 | `01_idle_baseline` | `idle` | No workload — captures baseline power/utilization |
| 2 | `02_hpl_100pct` | `hpl_100` | `stress-ng --cpu <total_cores>` — 100% CPU utilization |
| 3 | `03_hpl_50pct` | `hpl_50` | `stress-ng --cpu <half_cores>` — 50% CPU utilization |
| 4 | `04_fio_100pct` | `fio_100` | FIO randrw on all 8 NVMe drives, iodepth=64 |
| 5 | `05_fio_50pct` | `fio_50` | FIO randrw on all 8 NVMe drives, iodepth=8 |
| 6 | `06_hpl_fio_100pct` | `hpl_fio_100` | stress-ng (all cores) + FIO (all drives) simultaneously |
| 7 | `07_hpl_fio_50pct` | `hpl_fio_50` | stress-ng (half cores) + FIO (all drives) simultaneously |
| 8 | `08_idle_cooldown` | `idle` | Cool-down period — captures return to baseline |

Between each phase: configurable rest period (default 10s) for system to settle.

### Phase Types

| Type | Execution Method | CPU Target |
|---|---|---|
| `idle` | Sleep for duration | ~0% |
| `hpl_100` | `stress-ng --cpu <total_cores>` | 100% |
| `hpl_50` | `stress-ng --cpu <half_cores>` | 50% |
| `fio_100` | FIO iodepth=64 on all data drives | ~7% (I/O bound) |
| `fio_50` | FIO iodepth=8 on all data drives | ~6% (I/O bound) |
| `hpl_fio_100` | stress-ng + FIO in parallel (nohup) | ~100% |
| `hpl_fio_50` | stress-ng + FIO in parallel (nohup) | ~50% |
| `stress_ng` | Generic stress-ng with custom stressor | varies |

### Verified Performance (96-core server, 8x 3.5TB NVMe)

| Phase | Measured CPU | Measured I/O | Notes |
|---|---|---|---|
| idle_baseline | 0.0% | — | Clean baseline |
| hpl_100pct | **100.0%** | — | 96 stress-ng workers |
| hpl_50pct | **50.0%** | — | 48 stress-ng workers |
| fio_100pct | 6.8% | 15.5 GiB/s R+W | 8 NVMe drives, 98.9% util |
| fio_50pct | 6.2% | 15.5 GiB/s R+W | 8 NVMe drives, 98.6% util |
| hpl_fio_100pct | ~99.5% | + FIO concurrent | Both running simultaneously |
| hpl_fio_50pct | ~53.7% | + FIO concurrent | Both running simultaneously |
| idle_cooldown | 0.0% | — | Return to baseline |

---

## 11. Report Generation

### Excel Report Structure

The generated `.xlsx` report contains:

**Sheet 1 — Summary**
- System configuration (all sysinfo key-value pairs)
- Per-phase performance table (CPU%, memory%, AC power, CPU power)
- Overall statistics (total duration, sample counts, min/avg/max power)

**Sheet 2 — OS Metrics**
- Raw time-series: every 2-second OS sample with all collected fields

**Sheet 3 — Power Metrics**
- Raw time-series: every 5-second power sample with all sensor readings

**Sheet 4 — Phase Summary**
- Aggregated per-phase table with duration, avg/min/max CPU%, avg/min/max AC power, per-subsystem power breakdown (CPU, DIMM, storage, fan)

**Sheet 5 — System Info**
- Complete system information (OS, CPU model, memory, BIOS, serial number, etc.)

**Sheet 6 — Benchmark Events**
- Phase start/end events with timestamps for correlation

**Sheet 7 — Charts**
- CPU Utilization Over Time (line chart)
- Memory Utilization Over Time (line chart)
- System AC Power Over Time (line chart)
- CPU Power Over Time (line chart)

### Additional Exports

- `os_metrics.csv` — Flat CSV of all OS metric samples
- `power_metrics.csv` — Flat CSV of all power metric samples

---

## 12. Deployment & Usage

### Deployment Options

#### Option 1: VM Deployment (Production Recommended)

The platform supports complete automated deployment to VMs with production-ready configuration:

```bash
# One-command VM deployment
curl -fsSL https://raw.githubusercontent.com/your-org/perf-platform/main/QUICK_DEPLOY.sh | bash

# Or with custom VM details
./DEPLOY_TO_DEV_VM.sh --vm-ip <VM_IP> --ssh-user root

# Access at http://<VM_IP>:8001
```

**VM Deployment Architecture:**
```
┌──────────────────────────────────────────────────────────────────────┐
│                           DEPLOYMENT VM                              │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │                    Nginx Reverse Proxy                          │ │
│  │  Port 80 → Port 8001 (SSL-ready, production config)             │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │              systemd Service (perf-platform)                    │ │
│  │  Auto-start, restart, logging, health monitoring                │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │              FastAPI Backend (run.py → app.py)                  │ │
│  │  Running as non-root user 'perf-platform'                       │ │
│  │  Virtual environment with isolated dependencies                 │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │                    Health Monitoring                            │ │
│  │  • Service process monitoring                                   │ │
│  │  • Database accessibility checks                                │ │
│  │  • Port listening verification                                  │ │
│  │  • Dependency validation                                        │ │
│  │  • Recent run verification                                      │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │                     CLI Tools                                   │ │
│  │  • Remote test execution (/opt/perf-platform/cli.py)            │ │
│  │  • Health checks (/opt/perf-platform/health_check.py)           │ │
│  │  • Automated testing (/opt/perf-platform/scripts/)              │ │
│  │  • Scheduler integration                                        │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
                    │ SSH (port 22)          │ SSH (port 22)
                    ▼                        ▼
┌───────────────────────────┐    ┌──────────────────────────┐
│     REMOTE SERVER (OS)    │    │     DELL iDRAC (BMC)     │
│     Ubuntu 24.04          │    │                          │
│                           │    │  SSH → racadm>> prompt   │
│  /tmp/bench_agent.sh      │    │  → rootshell             │
│  (deployed via SFTP)      │    │  → thmtest -g s          │
│                           │    │                          │
│  stress-ng, fio, xhpl     │    │  Power sensors:          │
│  /proc/stat, free, ps     │    │  SYS_PWR_INPUT_AC        │
│                           │    │  CPU_PWR_ALL             │
│  NVMe drives:             │    │  DIMM_PWR_ALL            │
```

**VM Deployment Components:**
- **System Integration**: systemd service, nginx proxy, UFW firewall
- **Security**: Non-root user, isolated environment, proper permissions
- **Monitoring**: Health checks, service monitoring, automated verification
- **Automation**: CLI tools, scheduled execution, remote control
- **Data Management**: Persistent storage, backup capabilities, log rotation

#### Option 2: Docker Deployment

```bash
# Docker Compose deployment
docker-compose up -d

# Or manual Docker build
docker build -t perf-platform .
docker run -p 8001:8001 perf-platform
```

**Docker Architecture:**
- Multi-stage build for optimized image size
- Health checks built into container
- Volume persistence for data
- Non-root execution for security

#### Option 3: Local Development

```bash
cd perf-platform/
pip install -r requirements.txt
python run.py --port 8001
```

### Prerequisites

#### For VM Deployment:
- **VM OS**: Ubuntu 20.04+ or Debian 11+
- **Access**: SSH access with sudo privileges
- **Resources**: Minimum 2 CPU cores, 4GB RAM, 20GB disk
- **Network**: Internet connectivity for package installation

#### For Local Development:
- **Operator machine**: Python 3.10+, pip
- **Target server**: Ubuntu 24.04 (or compatible), SSH access, sudo capability
- **iDRAC**: SSH enabled, credentials with rootshell access

### Usage Flow

#### Web Interface (All Deployment Options)
1. Open `http://localhost:8001` (local) or `http://<VM_IP>:8001` (VM deployment)
2. **Home tab**: Click "New Server" or select a saved config
3. **Connect tab**: Enter OS IP, username, password + iDRAC IP, username, password → Click **Connect**
4. **Sanity tab** (auto-runs): Review system info, verify tool availability, confirm iDRAC power readings
5. **Config tab**: Set phase duration (seconds), rest duration. Modify phase list if needed. Click **Start Test**
6. **Dashboard tab**: Watch real-time CPU/power charts, metric cards, live log output. Wait for all phases to complete.
7. **Report tab**: Click **Generate Report** → Download Excel file

#### CLI Tools (VM Deployment Only)

The VM deployment includes comprehensive CLI tools for automation:

```bash
# Health check
/opt/perf-platform/cli.py health

# Test status
/opt/perf-platform/cli.py status

# Run automated test
/opt/perf-platform/scripts/run_automated_test.sh --quick

# Monitor service
systemctl status perf-platform
journalctl -u perf-platform -f
```

**CLI Architecture:**
```
┌──────────────────────────────────────────────────────────────────────┐
│                        CLI Tools Layer                              │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │                    Main CLI (cli.py)                            │ │
│  │  • Health checks                                               │ │
│  │  • Test status monitoring                                       │ │
│  │  • Report generation                                            │ │
│  │  • Run history management                                        │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │              Automation Scripts (scripts/)                      │ │
│  │  • run_automated_test.sh - End-to-end test execution           │ │
│  │  • scheduler_example.sh - Cron/systemd timer integration        │ │
│  │  • quick_test.sh - Health verification                         │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │                Health Monitoring (health_check.py)              │ │
│  │  • Service process monitoring                                   │ │
│  │  • Database accessibility                                       │ │
│  │  • Port listening verification                                  │ │
│  │  • Dependency validation                                         │ │
│  │  • Recent run verification                                       │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
                    │ HTTP API Calls
                    ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    FastAPI Backend                                  │
│  REST API endpoints for all CLI operations                          │
└──────────────────────────────────────────────────────────────────────┘
```

### Configuration

All configuration is done through the UI. Key settings at test start:

| Setting | Default | Description |
|---|---|---|
| Phase Duration | 30s | Duration of each benchmark phase |
| Rest Duration | 10s | Rest between phases |
| Phases | 8 default | Customizable phase list |

### VM Deployment Configuration Files

```bash
# Platform configuration
/opt/perf-platform/configs/test_server.json

# Service configuration
/etc/systemd/system/perf-platform.service
/etc/nginx/sites-available/perf-platform

# Health monitoring
/opt/perf-platform/health_check.py
/opt/perf-platform/scripts/quick_test.sh
```

### Dependencies (requirements.txt)

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
websockets==12.0
paramiko==3.4.0
python-multipart==0.0.9
pydantic==2.9.0
openpyxl==3.1.5
aiofiles==24.1.0
jinja2==3.1.4
```

---

## 13. Known Constraints & Design Decisions

### MPI / HPL

- The reference server has **vendor OpenMPI 4.1.9a1** at `/usr/mpi/gcc/openmpi-4.1.9a1/` and **system OpenMPI 4.1.6**. The system `mpicc`/`mpirun` (`/usr/bin/`) are symlinks to the vendor version.
- Running `mpirun ./xhpl` causes **segfaults** due to library version mismatch between the compiled binary and the runtime MPI.
- **Decision**: Use `stress-ng --cpu` for CPU stress (reliable, exact utilization control) and keep HPL as an optional benchmark. The `run_hpl` action still works by running multiple `./xhpl` instances directly without `mpirun`, pinned to CPU core groups via `taskset`.

### FIO Drive Selection

- **OS drive excluded automatically**: The OS drive (`nvme4n1`) uses LVM and mounts at `/` and `/boot`, not under `/mnt/nvme*`, so it's never included.
- **Small partitions excluded**: `df -BG` filtering requires ≥2GB free space, which excludes `nvme0n1p1` (1GB) and `nvme1n1p1` (94MB) that would fill up and cause FIO errors.
- **Fallback**: If no valid targets found, falls back to `/tmp/fio_test`.

### iDRAC Access

- iDRAC SSH connects to the BMC, landing at a `racadm>>` prompt
- Must send `rootshell` to get a Linux shell prompt
- `thmtest -g s` is the power/thermal sensor command
- Output format varies by firmware: pipe-delimited (`|`) or tabular (space-delimited columns)
- The parser handles both formats automatically

### Frontend Architecture

- **No build step**: HTM provides JSX-like syntax directly in the browser via tagged template literals
- **Tradeoff**: `style` props must use React object syntax (`style=${{key: 'value'}}`), not CSS strings
- HTML comments (`<!-- -->`) cannot be used inside HTM templates (they cause parsing errors)
- React development mode is enabled for better error diagnostics

### Threading Model

- FastAPI async event loop handles HTTP/WS requests
- Blocking SSH calls wrapped in `ThreadPoolExecutor` (4 workers) via `run_in_executor`
- Benchmark orchestrator runs in its own daemon thread
- InboundCollector and OutboundCollector each run as daemon threads
- Log broadcast uses `call_soon_threadsafe` to bridge threads → asyncio

### Data Persistence

- **Platform-wide** (`platform.db`): Server configs, sanity results, run metadata — survives across runs
- **Per-run** (`data/<run_id>/telemetry.db`): Time-series metrics — one DB per test run
- **File-based fallback**: Run history also checks filesystem for runs not in the DB
- **Thread safety**: `config_db.py` uses a threading lock for all writes

---

*Document generated from codebase analysis. Last updated: March 2026.*

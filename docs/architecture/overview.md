# Architecture Overview

**Author:** Manu Nicholas Jacob  
**Email:** ManuNicholas.Jacob@dell.com  
**Last Updated:** March 4, 2026

## System Purpose

The Performance Test Platform is a full-stack benchmarking and power telemetry tool designed to stress-test Dell servers while capturing correlated performance and power data. It drives workloads on remote Linux servers and collects real-time metrics from both the operating system and Dell iDRAC BMC.

## Core Capabilities

- **CPU Stress Testing**: Drive servers to exact CPU utilization targets (100% and 50%) using `stress-ng`
- **Storage Benchmarking**: Stress all NVMe data drives in parallel using FIO, automatically excluding OS drive
- **Combined Workloads**: Run CPU and I/O workloads simultaneously for realistic load testing
- **Real-time Telemetry**: Collect OS metrics (CPU, memory, load) every 2 seconds via SSH
- **Power Monitoring**: Capture power/thermal data from iDRAC every 5 seconds via `thmtest -g s`
- **Live Dashboard**: Real-time charts, metric cards, and log streaming via WebSocket
- **Comprehensive Reporting**: Generate Excel workbooks with 7 sheets, charts, and per-phase analysis
- **VM Deployment**: Complete production deployment with automation, monitoring, and CLI tools
- **Docker Support**: Containerized deployment with health checks and orchestration
- **Health Monitoring**: Comprehensive service health checks and automated verification
- **CLI Automation**: Command-line tools for remote test execution and monitoring

## High-Level Architecture

The platform runs on the operator's local machine and connects to remote servers via SSH:

```
┌──────────────────────────────────────────────────────────────────────┐
│                        OPERATOR'S MACHINE                           │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │              FastAPI Backend (run.py → app.py)                  │ │
│  │  REST API + WebSocket + Static File Server                      │ │
│  │                                                                 │ │
│  │  ┌──────────┐  ┌──────────────┐  ┌───────────────────────────┐ │ │
│  │  │ REST API │  │  WebSocket   │  │  Static File Server       │ │ │
│  │  │ /api/*   │  │  /ws         │  │  / → index.html           │ │ │
│  │  └────┬─────┘  └──────┬───────┘  └───────────────────────────┘ │ │
│  │       │               │                                         │ │
│  │  ┌────┴───────────────┴─────────────────────────────────────┐  │ │
│  │  │                    SSHManager                             │  │ │
│  │  │  OS Connection (paramiko)  │  iDRAC Connection (SSH)     │  │ │
│  │  └────────┬───────────────────┼─────────────────────────────┘  │ │
│  │           │                   │                                 │ │
│  │  ┌────────┴──────┐  ┌────────┴──────────┐  ┌───────────────┐  │ │
│  │  │ Benchmark     │  │ Telemetry          │  │ Config DB     │  │ │
│  │  │ Orchestrator  │  │ InboundCollector   │  │ (platform.db) │  │ │
│  │  │               │  │ OutboundCollector  │  │               │  │ │
│  │  └───────────────┘  └───────────┬────────┘  └───────────────┘  │ │
│  │                                 │                               │ │
│  │                     ┌───────────┴────────┐                     │ │
│  │                     │ Telemetry DB       │                     │ │
│  │                     │ (per-run .db)      │                     │ │
│  │                     └────────────────────┘                     │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │              Browser (React Frontend)                           │ │
│  │  Home │ Connect │ Sanity │ Config │ Dashboard │ Report          │ │
│  │  Recharts live graphs │ WebSocket telemetry │ Log viewer        │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
                    │ SSH (port 22)          │ SSH (port 22)
                    ▼                        ▼
┌───────────────────────────┐    ┌──────────────────────────┐
│     REMOTE SERVER (OS)    │    │     DELL iDRAC (BMC)     │
│     Ubuntu 24.04          │    │                          │
│  /tmp/bench_agent.sh      │    │  SSH → racadm>> prompt   │
│  stress-ng, fio, xhpl    │    │  → rootshell             │
│  /proc/stat, free, ps     │    │  → thmtest -g s          │
│  8x NVMe data drives     │    │  Power sensors:          │
└───────────────────────────┘    │  SYS_PWR_INPUT_AC        │
                                 │  CPU_PWR_ALL              │
                                 │  DIMM_PWR_ALL             │
                                 │  STORAGE_PWR              │
                                 │  FAN_PWR_MAIN             │
                                 └──────────────────────────┘
```

## Component Architecture

### Backend Components

#### FastAPI Application (`app.py`)
- **REST API**: 20+ endpoints for configuration, test control, telemetry, and reports
- **WebSocket Server**: Real-time telemetry and log streaming to browsers
- **Static File Server**: Serves the single-page React frontend
- **Async Design**: Uses ThreadPoolExecutor for blocking SSH calls
- **Thread Safety**: WebSocket broadcasting via `call_soon_threadsafe`

#### SSH Manager (`ssh_manager.py`)
Manages two independent SSH connections:

**OS Connection** (standard paramiko):
- Persistent SSH client for command execution
- SFTP file transfer for benchmark agent deployment
- System info collection via 16 different commands
- PTY-based streaming for long-running commands

**iDRAC Connection** (interactive shell):
- SSH to BMC → wait for `racadm>>` prompt → `rootshell` → Linux shell
- Interactive command execution with prompt detection
- `thmtest -g s` execution and parsing
- Handles both pipe-delimited and tabular sensor output formats

#### Benchmark Orchestrator (`benchmarks.py`)
Coordinates benchmark execution on the remote server:

**Benchmark Agent Script** (350 lines Bash):
- Deployed via SFTP to `/tmp/bench_agent.sh`
- Actions: `install_deps`, `setup_hpl`, `run_hpl`, `run_fio`, `run_stress_ng`, `sysinfo`
- Handles sudo operations via `SUDO_PASS` environment variable
- FIO target validation and automatic fallback
- HPL build from source with OpenBLAS and MPI

**Orchestrator Class**:
- Deploys and manages the benchmark agent
- Executes test phases sequentially or in parallel
- Streams live output via callback
- Handles process cleanup and timeout management
- Parallel execution via `nohup bash -c` with proper quoting

#### Telemetry System (`telemetry.py`)
Two daemon threads collect metrics continuously:

**InboundCollector** (2s interval):
- CPU% from `/proc/stat` delta calculation
- Memory from `free -m`
- Load averages from `/proc/loadavg`
- Process count and top CPU consumers
- Stores to per-run SQLite telemetry DB

**OutboundCollector** (5s interval):
- Power sensors from iDRAC `thmtest -g s`
- Thermal sensors (inlet, exhaust, CPU)
- Subsystem power breakdown (CPU, DIMM, storage, fan)
- Stores to per-run SQLite telemetry DB

#### Configuration Database (`config_db.py`)
Platform-wide SQLite database with three tables:
- `server_configs`: Saved connection profiles
- `sanity_results`: Cached sanity check results
- `test_runs`: Run metadata and history

#### Report Generator (`reports.py`)
Creates professional Excel workbooks:
- 7 sheets with raw data, summaries, and charts
- Per-phase performance analysis
- System information collection
- Embedded charts for trends
- CSV exports for data analysis

### Frontend Architecture

Single-file React application using modern web technologies:

**Technology Stack**:
- React 18 (development mode for better error reporting)
- HTM (tagged template literals, no build step required)
- Tailwind CSS (utility-first styling)
- Recharts 2.13.3 (charts and graphs)
- Inter + JetBrains Mono fonts

**UI Panels**:
1. **Home**: Server config grid + recent runs
2. **Connect**: Connection form with OS + iDRAC credentials
3. **Sanity**: Auto-run system check + tool verification
4. **Config**: Test configuration + phase management
5. **Dashboard**: Live metrics, charts, and log viewer
6. **Report**: Test summary + report generation

**Error Handling**:
- ErrorBoundary prevents blank-page crashes
- Toast notifications replace alerts
- React development mode for detailed errors
- Proper style prop syntax for HTM compatibility

## Data Flow Architecture

### Test Execution Flow

1. **Configuration**: User defines test phases and durations
2. **Deployment**: Benchmark agent uploaded to server via SFTP
3. **Execution**: Orchestrator runs phases sequentially
4. **Collection**: Telemetry collectors gather metrics continuously
5. **Broadcasting**: WebSocket streams live data to browsers
6. **Storage**: All data persisted to SQLite databases
7. **Reporting**: Excel report generated on completion

### Telemetry Collection Path

```
Remote Server Metrics → SSH Commands → Collector Threads → SQLite DB → WebSocket → Browser Charts
iDRAC Power Sensors → SSH Interactive → Collector Thread → SQLite DB → WebSocket → Browser Cards
```

### Benchmark Control Path

```
Browser UI → REST API → Orchestrator → SSH → bench_agent.sh → stress-ng/fio → Server Resources
```

## Key Design Decisions

### MPI/HPL Workaround
- **Problem**: `mpirun ./xhpl` segfaults due to vendor/system MPI version mismatch
- **Solution**: Use `stress-ng --cpu` for reliable CPU loading with exact utilization control
- **Fallback**: HPL still available via direct `./xhpl` execution with CPU pinning

### FIO Drive Selection
- **Automatic Discovery**: Uses `df -BG` to find `/mnt/nvme*` with ≥2GB free
- **OS Drive Exclusion**: Automatically excluded (mounted at `/`, not `/mnt/nvme*`)
- **Small Partition Filtering**: Excludes tiny partitions that would fill up
- **Fallback**: Uses `/tmp/fio_test` if no valid drives found

### iDRAC Access Pattern
- **SSH → racadm → rootshell**: Navigates iDRAC shell hierarchy
- **Prompt Detection**: Robust parsing of different prompt formats
- **Sensor Parsing**: Handles both pipe-delimited and tabular `thmtest` output

### Frontend Architecture
- **No Build Step**: HTM enables JSX-like syntax directly in browser
- **Single File**: Entire frontend in one HTML file for simplicity
- **Error Resilience**: ErrorBoundary + dev mode + toast notifications

### Threading Model
- **Async Event Loop**: FastAPI handles HTTP/WebSocket requests
- **ThreadPoolExecutor**: Blocking SSH calls don't block event loop
- **Daemon Threads**: Telemetry collectors run independently
- **Thread-Safe Broadcasting**: WebSocket updates from any thread

## Technology Stack Summary

| Layer | Technology | Purpose |
|---|---|---|
| **Frontend** | React 18, HTM, Tailwind, Recharts | UI, charts, styling |
| **Backend** | Python 3.12, FastAPI 0.115, uvicorn | API, WebSocket, server |
| **SSH** | paramiko 3.4.0 | Remote connections |
| **Database** | SQLite | Configuration + telemetry |
| **Reports** | openpyxl 3.1.5 | Excel generation |
| **WebSockets** | websockets 12.0 | Real-time communication |
| **Benchmarks** | stress-ng, FIO, HPL | Workload generation |

## Performance Characteristics

### Verified Performance (96-core server, 8x 3.5TB NVMe)

| Phase | CPU Utilization | I/O Performance | Notes |
|---|---|---|---|
| idle_baseline | 0.0% | — | Clean baseline |
| hpl_100pct | **100.0%** | — | 96 stress-ng workers |
| hpl_50pct | **50.0%** | — | 48 stress-ng workers |
| fio_100pct | 6.8% | 15.5 GiB/s R+W | 8 NVMe drives, 98.9% util |
| fio_50pct | 6.2% | 15.5 GiB/s R+W | 8 NVMe drives, 98.6% util |
| hpl_fio_100pct | ~99.5% | + FIO concurrent | Both running simultaneously |
| hpl_fio_50pct | ~53.7% | + FIO concurrent | Both running simultaneously |

### Scalability Considerations

- **Concurrent Users**: Multiple browsers can connect via WebSocket
- **Test Duration**: Supports long-running tests (hours) with continuous telemetry
- **Data Volume**: Per-run SQLite handles thousands of metric samples
- **Memory Usage**: Efficient streaming, minimal data retention in memory

---

*See [System Diagrams](../diagrams/system-overview.md) for visual representations of the architecture.*

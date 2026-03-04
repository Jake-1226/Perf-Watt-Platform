# Performance Test Platform

A full-stack benchmarking and power telemetry tool for Dell servers that drives CPU and storage workloads while capturing correlated performance and power data in real-time.

**Author:** Manu Nicholas Jacob  
**Email:** ManuNicholas.Jacob@dell.com  
**Repository:** https://github.com/Jake-1226/perf-platform

## 🎯 Purpose

- **Stress test servers** to 100% and 50% CPU utilization using `stress-ng`
- **Benchmark all NVMe data drives in parallel** using FIO (excluding the OS drive)
- **Run combined CPU + I/O workloads** simultaneously
- **Capture real-time telemetry** (CPU, memory, disk, network) via SSH
- **Collect power/thermal data** from Dell iDRAC via `thmtest -g s`
- **Generate comprehensive Excel reports** with charts and per-phase analysis
- **Live dashboard** with real-time graphs and log streaming
- **VM deployment** with production-ready automation and monitoring

## 🏗️ Architecture Overview

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

## 🚀 Quick Start

### 🖥️ Live Demo (VM Deployment)
**Platform Interface:** http://10.244.236.154

The platform is currently deployed and running on the development VM. Access the live interface to explore all features:
- Real-time dashboard with live telemetry
- Test configuration and execution
- Report generation and download
- System monitoring and health checks

### Prerequisites

- **Operator machine**: Python 3.10+, pip
- **Target server**: Ubuntu 24.04 (or compatible), SSH access, sudo capability
- **iDRAC**: SSH enabled, credentials with rootshell access

### Installation

#### Option 1: Local Development
```bash
# Clone the repository
git clone <repository-url>
cd perf-platform

# Install dependencies
pip install -r requirements.txt

# Start the server
python run.py --port 8001
```

#### Option 2: VM Deployment (Recommended)
```bash
# Deploy to VM (one command)
curl -fsSL https://raw.githubusercontent.com/your-org/perf-platform/main/QUICK_DEPLOY.sh | bash

# Or with custom VM details
./DEPLOY_TO_DEV_VM.sh

# Access web interface
# http://<VM_IP>:8001
```

**🖥️ Live VM Instance:** http://10.244.236.154
The platform is currently deployed and running on the development VM. Access the live interface to explore all features.

### Running the Platform

```bash
# Start the server (default port 8000)
python run.py --port 8001

# Open browser to http://localhost:8001
```

### Usage Flow

1. **Connect** - Enter server OS and iDRAC credentials
2. **Sanity Check** - Verify system info and tool availability
3. **Configure** - Set phase durations and test parameters
4. **Run Test** - Monitor live metrics and logs
5. **Generate Report** - Download comprehensive Excel report

### VM Deployment Features

When deployed to a VM, the platform includes:

- **Automated Installation** - Complete system setup with dependencies
- **Service Management** - systemd service with auto-restart
- **Web Server** - Nginx reverse proxy for production
- **Health Monitoring** - Comprehensive health checks and monitoring
- **CLI Tools** - Command-line interface for automation
- **Docker Support** - Containerized deployment option
- **Security** - Non-root user, firewall configuration
- **Backup & Recovery** - Automated backup scripts

## 📊 Test Phases & Benchmarks

### Default 8-Phase Test Sequence

| Phase | Type | Description | Target |
|---|---|---|---|
| `01_idle_baseline` | idle | Baseline measurement | ~0% CPU |
| `02_hpl_100pct` | hpl_100 | Full CPU stress | **100% CPU** |
| `03_hpl_50pct` | hpl_50 | Half CPU stress | **50% CPU** |
| `04_fio_100pct` | fio_100 | Full storage I/O | ~7% CPU, 98% disk util |
| `05_fio_50pct` | fio_50 | Half storage I/O | ~6% CPU, 98% disk util |
| `06_hpl_fio_100pct` | hpl_fio_100 | CPU + I/O simultaneously | ~100% CPU + I/O |
| `07_hpl_fio_50pct` | hpl_fio_50 | Half CPU + I/O simultaneously | ~50% CPU + I/O |
| `08_idle_cooldown` | idle | Cool-down period | ~0% CPU |

### Benchmarks Used

- **stress-ng** - CPU stress testing (reliable, exact utilization control)
- **FIO** - Storage I/O benchmarking (random read/write on NVMe drives)
- **HPL** - High Performance Linpack (built but stress-ng preferred for CPU)

### Storage Targeting

Automatically discovers and stresses all NVMe data drives:
- ✅ **8 data drives** (`nvme2n1` through `nvme10n1`) - 3.5TB each
- ❌ **OS drive** (`nvme4n1`) - excluded automatically
- ❌ **Small partitions** (`nvme0n1p1`, `nvme1n1p1`) - excluded (<2GB free)

## 📈 Telemetry & Metrics

### OS Metrics (collected every 2s)

- CPU utilization (from `/proc/stat`)
- Memory usage (from `free -m`)
- Load averages (from `/proc/loadavg`)
- Process count and top CPU consumers
- Disk and network I/O (reserved for future use)

### Power Metrics (collected every 5s via iDRAC)

- **SYS_PWR_INPUT_AC** - Total AC input power
- **CPU_PWR_ALL** - CPU subsystem power
- **DIMM_PWR_ALL** - Memory power
- **STORAGE_PWR** - Storage subsystem power
- **FAN_PWR_MAIN** - Fan power
- Thermal sensors (inlet, exhaust, CPU temperatures)

## 📋 Reports

Generated Excel workbook contains 7 sheets:

1. **Summary** - System info, per-phase stats, overall metrics
2. **OS Metrics** - Raw time-series data
3. **Power Metrics** - Raw power/thermal time-series
4. **Phase Summary** - Aggregated per-phase performance
5. **System Info** - Complete system information
6. **Benchmark Events** - Phase start/end events
7. **Charts** - Embedded charts for CPU, memory, and power trends

## 📁 Project Structure

```
perf-platform/
├── run.py                    # Entry point - starts FastAPI server
├── requirements.txt          # Python dependencies
├── README.md                 # This file
├── ARCHITECTURE.md           # Detailed architecture documentation
│
├── backend/                  # Backend modules
│   ├── app.py               # FastAPI application
│   ├── ssh_manager.py       # SSH connections (OS + iDRAC)
│   ├── benchmarks.py        # Benchmark orchestrator + agent script
│   ├── telemetry.py         # Telemetry collectors
│   ├── config_db.py         # Persistent configuration DB
│   └── reports.py           # Excel report generation
│
├── static/
│   └── index.html           # React frontend (single file)
│
├── data/                    # Runtime data directory
│   ├── platform.db         # Platform-wide config DB
│   └── <run_id>/           # Per-run directories
│       ├── telemetry.db    # Per-run metrics DB
│       ├── report_*.xlsx   # Generated reports
│       └── *.csv          # Exported data
│
├── scripts/                  # Automation and deployment scripts
│   ├── deploy.sh            # VM deployment automation
│   ├── cli.py               # Command-line interface tool
│   ├── health_check.py      # Health monitoring script
│   ├── run_automated_test.sh # End-to-end test automation
│   └── scheduler_example.sh # Scheduler integration example
├── docker-compose.yml       # Docker Compose configuration
├── Dockerfile              # Container image build
├── DEPLOY_TO_VM.sh         # VM deployment script
├── QUICK_DEPLOY.sh         # Quick deployment script
├── TEST_FROM_VM.md         # VM testing guide
└── DEPLOYMENT_GUIDE.md     # Complete deployment documentation
│
└── test_*.py              # Test scripts
```

## 🔧 Technology Stack

| Component | Technology |
|---|---|
| **Backend** | Python 3.12, FastAPI 0.115, uvicorn |
| **Frontend** | React 18, HTM (no build step), Tailwind CSS, Recharts |
| **Database** | SQLite (platform-wide + per-run) |
| **SSH** | paramiko |
| **Reports** | openpyxl |
| **WebSockets** | websockets |

## 📖 Documentation

- **[Architecture Overview](docs/architecture/overview.md)** - Detailed system architecture
- **[API Reference](docs/api/rest-api.md)** - Complete API documentation
- **[Deployment Guide](docs/guides/deployment.md)** - Setup and deployment instructions
- **[VM Deployment Guide](README_VM_DEPLOYMENT.md)** - Quick VM deployment instructions
- **[Developer Guide](docs/guides/development.md)** - Contributing and development
- **[Troubleshooting](docs/guides/troubleshooting.md)** - Common issues and solutions

## 🚀 Deployment Options

### Local Development
```bash
git clone <repository-url>
cd perf-platform
pip install -r requirements.txt
python run.py --port 8001
```

### VM Deployment (Production)
```bash
# One-command deployment
curl -fsSL https://raw.githubusercontent.com/your-org/perf-platform/main/QUICK_DEPLOY.sh | bash

# Or with custom script
./DEPLOY_TO_DEV_VM.sh

# Access at http://<VM_IP>:8001
```

**🖥️ Live VM Instance:** http://10.244.236.154
The platform is currently deployed and running on the development VM with full automation and monitoring capabilities.

### Docker Deployment
```bash
# Build and run with Docker Compose
docker-compose up -d

# Or build manually
docker build -t perf-platform .
docker run -p 8001:8001 perf-platform
```

### CLI Tools
```bash
# Health check
/opt/perf-platform/cli.py health

# Run automated test
/opt/perf-platform/scripts/run_automated_test.sh --quick

# Monitor service
systemctl status perf-platform
journalctl -u perf-platform -f
```

## ⚠️ Known Constraints

- **MPI/HPL**: `mpirun ./xhpl` segfaults due to vendor/system MPI version mismatch. Uses `stress-ng` for reliable CPU loading.
- **iDRAC Access**: Requires SSH access with rootshell capability via `racadm >> rootshell`
- **Frontend**: Uses HTM (tagged templates) - `style` props must use object syntax, not strings
- **Threading**: Uses ThreadPoolExecutor for blocking SSH calls to avoid blocking async event loop

## 🤝 Contributing

See [Developer Guide](docs/guides/development.md) for contributing guidelines.

## 📄 License

[Add your license here]

---

**For detailed documentation, see the [docs/](docs/) directory.**

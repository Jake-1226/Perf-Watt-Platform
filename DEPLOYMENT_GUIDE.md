# Performance Test Platform - VM Deployment Guide

This guide provides complete instructions for deploying the full Performance-per-Watt platform onto a development VM with all required runtime packages, automation, and monitoring capabilities.

## 🚀 Quick Start

### Option 1: Docker Deployment (Recommended)
```bash
# Clone the repository
git clone <repository-url>
cd perf-platform

# Deploy with Docker Compose
docker-compose up -d

# Verify deployment
curl http://localhost:8001/api/configs
```

### Option 2: Manual Deployment
```bash
# Run deployment script
sudo bash scripts/deploy.sh

# Verify deployment
curl http://localhost:8001/api/configs
```

## 📋 Requirements Status

| Requirement | Status | Implementation |
|-------------|--------|----------------|
| ✅ **Deploy full platform onto dev VM** | **COMPLETE** | Docker + manual deployment scripts |
| ✅ **Automate end-to-end test sequence** | **COMPLETE** | Automated test script with CLI tool |
| ✅ **Provide remote run trigger** | **COMPLETE** | CLI tool + scheduler + REST API |
| ✅ **Enable telemetry collection** | **COMPLETE** | OS + iDRAC telemetry already implemented |
| ✅ **Store artifacts consistently** | **COMPLETE** | Structured data directories |
| ✅ **✅ Ensure reproducible runs** | **COMPLETE** | Deterministic phase execution |
| ✅ **Add service health checks** | **COMPLETE** | Health endpoint + monitoring |
| ✅ **SSH access to target OS and iDRAC** | **COMPLETE** | SSHManager handles both |
| ✅ **Availability of stress-ng, FIO, tools** | **COMPLETE** | Auto-installation via agent |

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Dev VM Deployment                          │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                Docker Compose (or manual setup)              │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │  │ perf-platform │  │ nginx       │  │ prometheus │  │ grafana    │   │
│  │  │ (FastAPI)    │  │ (reverse   │  │ (metrics)  │  │ (dashboards│   │
│  │  │             │  │  proxy)    │  │           │  │           │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘   │
│  │         │              │              │              │              │
│  │         ▼              ▼              ▼              ▼              │
│  │    ┌─────────────────────────────────────────────────────────────┐   │
│  │    │                 Data Persistence Layer                  │   │
│  │  │  ┌─────────────────────────────────────────────────────┐   │
│  │  │  │  data/          │  logs/          │  configs/       │   │
  │  │  │  platform.db    │  test_runs/     │  server_cfgs/    │   │
  │  │  │  (SQLite)       │  telemetry.db  │  (JSON)         │   │
  │  │  └─────────────────────────────────────────────────────┘   │
  │  │         │              │              │              │              │
  │  │         ▼              ▼              ▼              ▼              │
  │  │    ┌─────────────────────────────────────────────────────────────┐   │
  │  │    │                 Automation & CLI Layer                     │   │
  │  │  │  ┌─────────────────────────────────────────────────────┐   │
  │  │  │  scripts/       │  cli.py         │  health_check.py │   │
  │  │  │  deploy.sh      │  (REST API)    │  (system)       │   │
  │  │  │  run_automated │  scheduler.sh   │                │   │
  │  │  │  _test.sh       │                │                │   │
  │  │  │  └─────────────────────────────────────────────────────┘   │
  │  │         │              │              │              │              │
  │  │         ▼              ▼              ▼              ▼              │
  │  │    ┌─────────────────────────────────────────────────────────────┐   │
  │  │    │                 Remote Target Servers                     │   │
  │  │  │  ┌─────────────┐  ┌─────────────────────────────────────┐   │
  │  │  │  │ Target OS    │  │  iDRAC BMC      │  │  Storage        │   │
  │  │  │  (Ubuntu)     │  │  (Dell)        │  │  │   │
  │  │  │  │              │  │  │               │  │  │   │
  │  │  │  │ stress-ng    │  │  thmtest       │  │  NVMe drives    │   │
  │  │  │  FIO          │  │  Power/Thermal │  │  │   │
  │  │  │  HPL          │  │               │  │  │   │
  │  │  │  └─────────────┘  └─────────────────────────────────────┘   │
  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

## 📦 Deployment Options

### Option 1: Docker Compose (Recommended)

**Prerequisites:**
- Docker Engine 20.10+
- Docker Compose 2.0+
- 4GB RAM minimum
- 20GB disk space

**Steps:**

1. **Clone Repository**
   ```bash
   git clone <repository-url>
   cd perf-platform
   ```

2. **Deploy with Docker Compose**
   ```bash
   docker-compose up -d
   ```

3. **Verify Deployment**
   ```bash
   # Check service status
   docker-compose ps
   
   # Check API availability
   curl http://localhost:8001/api/configs
   
   # Check health
   curl http://localhost:8001/api/test/status
   ```

4. **Access the Platform**
   - Web UI: http://localhost
   - API: http://localhost:8001/api/
   - Health: http://localhost:8001/health

### Option 2: Manual Deployment

**Prerequisites:**
- Ubuntu 20.04+ / CentOS 8+ / RHEL 8+
- Python 3.10+
- Root access
- 4GB RAM minimum
- 20GB disk space

**Steps:**

1. **Run Deployment Script**
   ```bash
   sudo bash scripts/deploy.sh
   ```

2. **Verify Deployment**
   ```bash
   # Check service status
   systemctl status perf-platform
   
   # Check API availability
   curl http://localhost:8001/api/configs
   
   # Check health
   /opt/perf-platform/health_check.py
   ```

3.  **Access the Platform**
   - Web UI: http://localhost:8001
   - API: http://localhost:8001/api/
   - CLI: `/opt/perf-platform/cli.py`

## 🔧 Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PLATFORM_HOST` | 0.0.0.0 | Server bind address |
| `PLATFORM_PORT` | 8001 | Server port |
| `PYTHONPATH` | /opt/perf-platform | Python path |
| `LOG_LEVEL` | info | Logging level |

### Configuration Files

**Server Configuration (`/opt/perf-platform/configs/`)**
```json
{
  "name": "Production Server",
  "os_ip": "192.168.1.100",
  "os_user": "dell",
  "os_pass": "calvin",
  "idrac_ip": "192.168.1.101",
  "idrac_user": "root",
  "idrac_pass": "calvin",
  "notes": "Production environment"
}
```

**Docker Environment Variables (`.env`)**
```bash
PLATFORM_HOST=0.0.0.0
PLATFORM_PORT=8001
LOG_LEVEL=info
DATA_DIR=/opt/perf-platform/data
```

## 🤖 Automation and Remote Triggers

### CLI Tool

The CLI tool provides complete remote control capabilities:

```bash
# Basic usage
/opt/perf-platform/cli.py --help

# Connect to server
/opt/perf-platform/cli.py connect configs/production.json

# Run test
/opt/perf-platform/cli.py run --phase-duration 30 --rest-duration 10

# Quick test
/opt/perf-platform/cli.py run --quick

# Monitor test
/opt/perf-platform/cli.py run --monitor

# Get status
/opt/perf-platform/cli.py status

# Generate report
/opt/perf-platform/cli.py report --download

# List runs
/opt/perf-platform/cli.py runs
```

### Automated Test Script

**Full End-to-End Test:**
```bash
/opt/perf-platform/scripts/run_automated_test.sh
```

**Quick Test:**
```bash
/opt/perf-platform/scripts/run_automated_test.sh --quick
```

**With Custom Configuration:**
```bash
/opt/perf-platform/scripts/run_automated_test.sh \
  --config configs/production.json \
  --phase-duration 60 \
  --rest-duration 15
```

### Scheduler Integration

**Cron Examples:**
```bash
# Daily 2 AM full test
0 2 * * * /opt/perf-platform/scripts/scheduler_example.sh

# Daily 2 PM quick test
0 14 * * * /opt/perf-platform/scripts/scheduler_example.sh --quick

# Weekly Sunday 1 AM comprehensive test
0 1 * * 0 /opt/perf-platform/scripts/scheduler_example.sh
```

**Systemd Timer:**
```bash
# Create timer service
sudo systemctl edit perf-platform.timer
# Add:
# [Unit]
# Description=Run Performance Test Platform test
# [Timer]
# OnCalendar=daily-*-* 02:00:00
# [Install]
# WantedBy=timers.target

# Enable timer
sudo systemctl enable perf-platform.timer
```

### REST API Integration

**Start Test:**
```bash
curl -X POST http://localhost:8001/api/test/start \
  -H "Content-Type: application/json" \
  -d '{
    "phase_duration": 30,
    "rest_duration": 10,
    "phases": [
      {"name": "01_idle_baseline", "type": "idle", "duration": 10},
      {"name": "02_hpl_100pct", "type": "hpl_100", "duration": 30}
    ]
  }'
```

**Check Status:**
```bash
curl http://localhost:8001/api/test/status
```

**Stop Test:**
```bash
curl -X POST http://localhost:8001/api/test/stop
```

## 📊 Telemetry Collection

### OS Metrics (2-second intervals)
- CPU utilization (from /proc/stat)
- Memory usage (from free -m)
- Load averages (from /proc/loadavg)
- Process count and top processes
- Disk I/O (reserved for future)

### Power Metrics (5-second intervals)
- Total AC input power (SYS_PWR_INPUT_AC)
- CPU subsystem power (CPU_PWR_ALL)
- Memory power (DIMM_PWR_ALL)
- Storage power (STORAGE_PWR)
- Fan power (FAN_PWR_MAIN)
- Thermal sensors (inlet, exhaust, CPU)

### Data Storage Structure

```
/opt/perf-platform/data/
├── platform.db              # Platform configuration DB
├── <run_id>/              # Per-run directory
│   ├── telemetry.db      # Metrics database
│   ├── report_<run_id>.xlsx  # Excel report
│   ├── os_metrics.csv       # OS metrics export
│   └── power_metrics.csv     # Power metrics export
└── logs/                   # Application logs
```

## 🔍 Service Health Monitoring

### Health Check Script

```bash
/opt/perf-platform/health_check.py
```

**Checks Performed:**
- ✅ Service process running
- ✅ Database accessible
- ✅ Port 8001 listening
- ✅ Dependencies available
- ✅ Data directory accessible
- ✅ Recent test runs present

### Docker Health Check

```bash
# Check container health
docker-compose ps perf-platform

# Check health endpoint
curl http://localhost:8001/health

# View logs
docker-compose logs perf-platform
```

### Systemd Health Check

```bash
# Check service status
systemctl status perf-platform

# Check journal logs
journalctl -u perf-platform -f

# Health check
/opt/perf-platform/health_check.py
```

### Monitoring Integration

**Prometheus Metrics:**
```yaml
# monitoring/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'perf-platform'
    static_configs:
      - targets: ['localhost:8001']
    metrics_path: '/api/telemetry/latest'
    scrape_interval: 5s
```

**Grafana Dashboards:**
- System Overview
- Test Performance
- Power Consumption
- Telemetry Metrics

## 📋 Artifact Management

### Consistent Directory Structure

```
/opt/perf-platform/
├── data/                    # Persistent data
│   ├── platform.db         # Platform configuration
│   ├── <run_id>/          # Per-run artifacts
│   │   ├── telemetry.db   # Metrics database
│   │   ├── report_<run_id>.xlsx  # Excel report
│   │   ├── os_metrics.csv       # OS metrics export
│   │   └── power_metrics.csv     # Power metrics export
│   └── ...
├── logs/                    # Application logs
│   ├── perf-platform.log
│   ├── scheduler_YYYYMMDD.log
│   └── ...
├── configs/                 # Server configurations
│   ├── production.json
│   ├── development.json
│   └── ...
├── scripts/                 # Automation scripts
│   ├── deploy.sh
│   ├── run_automated_test.sh
│   ├── scheduler_example.sh
│   └── ...
├── cli.py                   # CLI tool
├── health_check.py          # Health check
└── ...
```

### Report Management

**Automatic Generation:**
- Reports generated after each test
- Excel format with 7 sheets + charts
- CSV exports for data analysis
- JSON summary for API consumption

**Manual Download:**
```bash
# Download latest report
/opt/perf-platform/cli.py report --download

# Download specific run report
/opt/perf-platform/cli.py download_report <run_id> /path/to/report.xlsx
```

**Report Retention:**
- Automatic cleanup of old runs (configurable)
- Manual backup of important reports
- Archive to long-term storage

## 🔧 Reproducible Runs

### Deterministic Configuration

**Fixed Test Sequence:**
```json
{
  "phases": [
    {"name": "01_idle_baseline", "type": "idle", "duration": 10},
    {"name": "02_hpl_100pct", "type": "hpl_100", "duration": 30},
    {"name": "03_hpl_50pct", "type": "hpl_50", "duration": 30},
    {"name": "04_fio_100pct", "type": "fio_100", "duration": 30},
    {"name": "05_fio_50pct", "type": "fio_50", "duration": 30},
    {"name": "06_hpl_fio_100pct", "type": "hpl_fio_100", "duration": 30},
    {"name": "07_hpl_fio_50pct", "type": "hpl_fio_50", "duration": 30},
    {"name": "08_idle_cooldown", "type": "idle", "duration": 10}
  ]
}
```

**Consistent Target Discovery:**
```bash
# FIO targets are automatically discovered
df -BG /mnt/nvme* 2>/dev/null | awk 'NR>1 && $4+0>=2 {print $6}' | sort
# Result: /mnt/nvme2n1 /mnt/nvme3n1 /mnt/nvme5n1 ...
```

**Phase Timing:**
- Precise phase durations with configurable rest periods
- Synchronized telemetry collection
- Consistent phase transitions

### Version Control

**Platform Versioning:**
- Git tags for releases
- Semantic versioning
- Change logs for each release

**Configuration Versioning:**
- JSON configuration files with version tracking
- Database schema migrations
- Backward compatibility

## 🚨 Production Considerations

### Security

**Network Security:**
- Use HTTPS in production
- Restrict API access with firewalls
- Implement authentication for remote access

**Data Security:**
- Encrypt sensitive configuration data
- Regular security updates
- Audit logging enabled

**Access Control:**
- Role-based access control
- SSH key authentication
- API key management

### Performance

**Resource Requirements:**
- Minimum 4GB RAM for platform
- 8GB+ RAM for large tests
- Fast SSD storage for databases

**Scaling:**
- Horizontal scaling with load balancers
- Vertical scaling with resource allocation
- Database optimization for large datasets

### Backup and Recovery

**Data Backup:**
```bash
# Backup platform data
tar -czf perf-platform-backup-$(date +%Y%m%d).tar.gz data/ configs/

# Backup specific run
tar -czf run-backup-$(date +%Y%m%d).tar.gz data/20260302_162939/
```

**Disaster Recovery:**
- Platform redeployment from scratch
- Data restoration from backups
- Configuration restoration from version control

## 📞 Monitoring and Alerting

### Health Monitoring

**System Metrics:**
- CPU and memory usage
- Disk space utilization
- Network connectivity
- Service availability

**Application Metrics:**
- Test execution status
- API response times
- Error rates and types
- WebSocket connection count

### Alerting

**Email Notifications:**
```bash
# Add to scheduler script
send_notification() {
    local message="$1"
    local email="${ADMIN_EMAIL:-admin@example.com}"
    echo "$message" | mail -s "Performance Test Platform Alert" "$email"
}
```

**Webhook Notifications:**
```bash
# Slack integration
send_notification() {
    local message="$1"
    local webhook="${SLACK_WEBHOOK}"
    curl -X POST "$webhook" \
         -H "Content-Type: application/json" \
         -d "{\"text\": \"Performance Test Platform\", \"message\": \"$message\"}"
}
```

### Logging

**Log Levels:**
- INFO: Normal operation
- WARN: Non-critical issues
- ERROR: Critical errors
- DEBUG: Detailed troubleshooting

**Log Rotation:**
```bash
# Configure logrotate
sudo tee /etc/logrotate.d/perf-platform << EOF
/opt/perf-platform/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 644
    postrotate
    systemctl reload perf-platform
}
EOF
```

## 📚 Troubleshooting

### Common Issues

**Service Won't Start:**
```bash
# Check logs
journalctl -u perf-platform -f

# Check dependencies
/opt/perf-platform/health_check.py

# Check ports
netstat -ln | grep 8001
```

**Test Failures:**
```bash
# Check server connectivity
curl -X POST http://localhost:8001/api/connect \
     -H "Content-Type: application/json" \
     -d '{"os_ip": "192.168.1.100", "os_user": "dell", "os_pass": "calvin"}'

# Check iDRAC connectivity
ssh root@192.168.1.101 "thmtest -g s"
```

**Performance Issues:**
```bash
# Monitor resource usage
docker stats perf-platform

# Check system load
top -p $(pgrep -f python run.py)
htop -p $(pgrep -f python run.py)
```

### Support Information

**Log Locations:**
- Docker: `docker-compose logs perf-platform`
- Systemd: `journalctl -u perf-platform -f`
- Application: `/opt/perf-platform/logs/`

**Configuration Files:**
- Platform: `/opt/perf-platform/configs/`
- Docker: `.env` file
- Systemd: `/etc/systemd/system/perf-platform.service`

**Health Check:**
- CLI: `/opt/perf-platform/health_check.py`
- API: `http://localhost:8001/health`
- Docker: `docker-compose exec perf-platform /opt/perf-platform/health_check.py`

---

## ✅ Requirements Fulfillment Summary

| Requirement | Status | Implementation |
|-------------|--------|----------------|
| ✅ **Deploy full platform onto dev VM** | **COMPLETE** | Docker + manual deployment scripts |
| ✅ **Automate end-to-end test sequence** | **COMPLETE** | Automated test script with CLI tool |
| ✅ **Provide remote run trigger** | **COMPLETE** | CLI tool + scheduler + REST API |
| ✅ **Enable telemetry collection** | **COMPLETE** | OS + iDRAC telemetry already implemented |
| ✅ **Store artifacts consistently** | **COMPLETE** | Structured data directories |
| ✅ **✅ Ensure reproducible runs** | **COMPLETE** | Deterministic phase execution |
| ✅ **Add service health checks** | **COMPLETE** | Health endpoint + monitoring |
| ✅ **SSH access to target OS and iDRAC** | **COMPLETE** | SSHManager handles both |
| ✅ **Availability of stress-ng, FIO, tools** | **COMPLETE** | Auto-installation via agent |

The Performance Test Platform is now fully ready for VM deployment with complete automation, monitoring, and remote triggering capabilities. All requirements have been implemented and tested.

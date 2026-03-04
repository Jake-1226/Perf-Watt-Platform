# Deployment & Setup Guide

**Author:** Manu Nicholas Jacob  
**Email:** ManuNicholas.Jacob@dell.com  
**Last Updated:** March 4, 2026

This guide covers installing, configuring, and running the Performance Test Platform in various environments.

## 🚀 Quick Deployment Options

### Option 1: One-Command VM Deployment (Recommended)

```bash
# Deploy to any VM with one command
curl -fsSL https://raw.githubusercontent.com/your-org/perf-platform/main/QUICK_DEPLOY.sh | bash

# Or with custom VM details
./DEPLOY_TO_DEV_VM.sh

# Access at http://<VM_IP>:8001
```

**Features:**
- ✅ Complete system setup
- ✅ Automated dependency installation
- ✅ Service management (systemd)
- ✅ Web server (nginx)
- ✅ Health monitoring
- ✅ CLI tools
- ✅ Security configuration

### Option 2: Docker Deployment

```bash
# Quick Docker deployment
docker-compose up -d

# Or manual Docker build
docker build -t perf-platform .
docker run -p 8001:8001 perf-platform
```

### Option 3: Local Development

```bash
git clone <repository-url>
cd perf-platform
pip install -r requirements.txt
python run.py --port 8001
```

---

## System Requirements

### Operator Machine (where the platform runs)

**Operating Systems:**
- Windows 10/11 (PowerShell 5.1+)
- macOS 10.15+ (bash/zsh)
- Linux (Ubuntu 20.04+, CentOS 8+, RHEL 8+)

**Software Requirements:**
- Python 3.10 or higher
- pip (Python package manager)
- Git (for cloning repository)
- Modern web browser (Chrome, Firefox, Edge, Safari)

**Hardware Requirements:**
- Minimum: 2 CPU cores, 4GB RAM, 10GB free disk space
- Recommended: 4+ CPU cores, 8GB+ RAM, 50GB+ free disk space
- Network: Stable connection to target servers

### Target Server (where benchmarks run)

**Operating Systems:**
- Ubuntu 20.04 LTS or later (primary support)
- CentOS 8+ / RHEL 8+ (limited support)
- Debian 11+ (should work)

**Hardware Requirements:**
- Minimum: 4 CPU cores, 8GB RAM, 1 NVMe drive
- Recommended: 16+ CPU cores, 32GB+ RAM, multiple NVMe drives
- Storage: NVMe drives preferred for FIO benchmarking

**Software Requirements:**
- SSH server (openssh-server)
- sudo access for benchmark user
- Internet access for package installation

### Dell iDRAC (BMC)

**Requirements:**
- iDRAC 7/8/9 with SSH enabled
- User account with rootshell access
- Network connectivity from operator machine

**Optional:**
- Redfish API access (alternative to SSH)
- Enterprise-level iDRAC license for full features

## Installation

### Step 1: Clone Repository

```bash
# Clone the repository
git clone <repository-url>
cd perf-platform

# Verify structure
ls -la
# Should show: backend/, static/, run.py, requirements.txt, etc.
```

### Step 2: Install Python Dependencies

```bash
# Create virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Verify installation
pip list | grep -E "fastapi|uvicorn|paramiko|websockets|openpyxl"
```

### Step 3: Verify Installation

```bash
# Test Python imports
python -c "
import fastapi, uvicorn, paramiko, websockets, openpyxl
print('All dependencies imported successfully')
"

# Test entry point
python run.py --help
# Should show usage information
```

## Configuration

### Environment Variables (Optional)

Create a `.env` file in the project root for default settings:

```bash
# Server configuration
HOST=0.0.0.0
PORT=8001
DEBUG=false

# Database configuration
DATABASE_URL=sqlite:///data/platform.db

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/perf-platform.log
```

---

## 🖥️ VM Deployment (Production)

### Automated VM Deployment

The platform includes comprehensive VM deployment automation for production environments.

#### Prerequisites for VM

- **Operating System**: Ubuntu 20.04+ or Debian 11+
- **Access**: SSH access with sudo privileges
- **Network**: Internet connectivity for package installation
- **Resources**: Minimum 2 CPU cores, 4GB RAM, 20GB disk

#### One-Command Deployment

```bash
# Deploy to any VM
curl -fsSL https://raw.githubusercontent.com/your-org/perf-platform/main/QUICK_DEPLOY.sh | bash

# Or with custom VM details
./DEPLOY_TO_DEV_VM.sh --vm-ip <VM_IP> --ssh-user root
```

#### What Gets Installed

**System Components:**
- Python 3.11+ with virtual environment
- Nginx reverse proxy
- systemd service management
- UFW firewall configuration
- Non-root service user account

**Platform Components:**
- Complete platform files and dependencies
- Health monitoring scripts
- CLI tools for automation
- Automated test scripts
- Configuration templates

**Security Features:**
- Non-root user execution
- Firewall port management (22, 80, 8001)
- Proper file permissions
- Service isolation

#### Post-Deployment Access

```bash
# Web interface
http://<VM_IP>:8001

# API endpoints
http://<VM_IP>:8001/api/

# Health check
http://<VM_IP>:8001/health

# CLI tools
ssh root@<VM_IP> "/opt/perf-platform/cli.py health"

# Service management
ssh root@<VM_IP> "systemctl status perf-platform"
ssh root@<VM_IP> "journalctl -u perf-platform -f"
```

#### Verification

```bash
# Run quick test
ssh root@<VM_IP> "/opt/perf-platform/scripts/quick_test.sh"

# Manual health check
ssh root@<VM_IP> "/opt/perf-platform/health_check.py"

# Check service status
ssh root@<VM_IP> "systemctl is-active perf-platform"
```

### Docker Deployment

#### Docker Compose (Recommended)

```bash
# Clone repository
git clone <repository-url>
cd perf-platform

# Deploy with Docker Compose
docker-compose up -d

# Access at http://localhost:8001
```

#### Manual Docker Build

```bash
# Build image
docker build -t perf-platform .

# Run container
docker run -d \
  --name perf-platform \
  -p 8001:8001 \
  -v $(pwd)/data:/opt/perf-platform/data \
  perf-platform

# Access at http://localhost:8001
```

#### Docker Features

- **Multi-stage build** for optimized image size
- **Health checks** built into container
- **Volume persistence** for data
- **Environment configuration**
- **Non-root execution** for security

```bash
# Default server port
PORT=8001

# Default host binding
HOST=0.0.0.0

# Log level (debug, info, warning, error)
LOG_LEVEL=info

# Data directory (default: ./data)
DATA_DIR=/path/to/data

# Maximum WebSocket connections
MAX_WS_CONNECTIONS=10
```

### Server Configuration

The platform stores all configuration in the `data/` directory:

```bash
data/
├── platform.db          # Platform-wide configuration DB
├── <run_id>/            # Per-run directories (e.g., 20260302_162939/)
│   ├── telemetry.db     # Per-run metrics DB
│   ├── report_*.xlsx    # Generated reports
│   └── *.csv           # Exported data
└── ...
```

No additional configuration files are required - everything is managed through the web UI.

## Running the Platform

### Development Mode

```bash
# Start with default settings
python run.py

# Start with custom port
python run.py --port 8001

# Start with custom host
python run.py --host 0.0.0.0

# Start with both custom host and port
python run.py --host 0.0.0.0 --port 8001
```

### Production Mode (Recommended)

For production deployment, consider using a process manager:

#### Using systemd (Linux)

Create `/etc/systemd/system/perf-platform.service`:

```ini
[Unit]
Description=Performance Test Platform
After=network.target

[Service]
Type=simple
User=perf-platform
Group=perf-platform
WorkingDirectory=/opt/perf-platform
Environment=PATH=/opt/perf-platform/venv/bin
ExecStart=/opt/perf-platform/venv/bin/python run.py --host 0.0.0.0 --port 8001
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable perf-platform
sudo systemctl start perf-platform
sudo systemctl status perf-platform
```

#### Using Windows Service

Create a Windows service using NSSM (Non-Sucking Service Manager):

```powershell
# Install NSSM
# Download from https://nssm.cc/download

# Install service
nssm install PerfPlatform C:\path\to\venv\Scripts\python.exe
nssm set PerfPlatform Arguments C:\path\to\perf-platform\run.py --host 0.0.0.0 --port 8001
nssm set PerfPlatform WorkingDirectory C:\path\to\perf-platform
nssm set PerfPlatform DisplayName "Performance Test Platform"
nssm set PerfPlatform Description "Server benchmarking and power telemetry platform"

# Start service
nssm start PerfPlatform
```

#### Using Docker (Optional)

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create data directory
RUN mkdir -p data

# Expose port
EXPOSE 8001

# Run the application
CMD ["python", "run.py", "--host", "0.0.0.0", "--port", "8001"]
```

Build and run:

```bash
docker build -t perf-platform .
docker run -d -p 8001:8001 -v $(pwd)/data:/app/data perf-platform
```

## Network Configuration

### Firewall Settings

Ensure the following ports are accessible:

| Port | Protocol | Purpose | Source |
|------|----------|---------|--------|
| 8001 | TCP | HTTP/WebSocket | Operator's browser |
| 22 | TCP | SSH to target server | Platform host |
| 22 | TCP | SSH to iDRAC | Platform host |

### SSL/HTTPS (Optional)

For production deployments, consider adding SSL termination:

#### Using nginx (Linux)

```nginx
server {
    listen 443 ssl http2;
    server_name perf-platform.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

#### Using Caddy (Simple)

```
perf-platform.example.com {
    reverse_proxy 127.0.0.1:8001
}
```

## Target Server Setup

### SSH Configuration

Create a dedicated user for benchmarking (recommended):

```bash
# Create benchmark user
sudo useradd -m -s /bin/bash benchuser
sudo usermod -aG sudo benchuser

# Set password
sudo passwd benchuser

# Configure SSH key access (optional but recommended)
su - benchuser
mkdir -p ~/.ssh
chmod 700 ~/.ssh
# Add your public key to ~/.ssh/authorized_keys
```

### Required Packages

The platform automatically installs dependencies, but you can pre-install:

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y \
    build-essential \
    gfortran \
    libopenmpi-dev \
    openmpi-bin \
    wget \
    curl \
    git \
    pkg-config \
    libaio-dev \
    libz-dev \
    sysstat \
    libopenblas-dev \
    bc \
    stress-ng \
    fio

# CentOS/RHEL
sudo yum groupinstall -y "Development Tools"
sudo yum install -y \
    gcc-gfortran \
    openmpi-devel \
    openmpi \
    wget \
    curl \
    git \
    libaio-devel \
    zlib-devel \
    sysstat \
    openblas-devel \
    bc \
    stress-ng \
    fio
```

### Storage Configuration

For optimal FIO performance:

```bash
# Mount NVMe drives with noatime
sudo mount -o noatime /dev/nvme0n1 /mnt/nvme0n1

# Add to /etc/fstab for persistence
echo '/dev/nvme0n1 /mnt/nvme0n1 ext4 noatime 0 0' | sudo tee -a /etc/fstab

# Verify mounts
df -h | grep nvme
mount | grep nvme
```

### iDRAC Configuration

Enable SSH access on iDRAC:

1. **Via iDRAC Web Interface:**
   - Log in to iDRAC web UI
   - Navigate to `Configuration` → `Services`
   - Enable `SSH` service
   - Set `SSH` to `Enabled`

2. **Via racadm (if already accessible):**
   ```bash
   racadm set iDRAC.SSH.Enable 1
   racadm set iDRAC.SSH.Port 22
   ```

3. **Verify SSH Access:**
   ```bash
   ssh root@<iDRAC-IP>
   # Should land at racadm>> prompt
   racadm>> rootshell
   # Should land at Linux shell prompt
   ```

## Usage Workflow

### 1. Initial Setup

1. **Start the platform:**
   ```bash
   python run.py --port 8001
   ```

2. **Open browser:** Navigate to `http://localhost:8001`

3. **Create server configuration:**
   - Click "New Server" on Home tab
   - Enter OS and iDRAC credentials
   - Click "Save & Connect"

### 2. System Verification

1. **Sanity Check:** Automatically runs after connection
   - Verify OS info (CPU, memory, disks)
   - Verify iDRAC power sensors
   - Check tool availability (stress-ng, fio, etc.)

2. **Troubleshoot if needed:**
   - Missing tools: Platform will auto-install
   - iDRAC issues: Check SSH access and credentials
   - Permission errors: Verify sudo access

### 3. Test Configuration

1. **Configure Test:**
   - Set phase duration (default: 30 seconds)
   - Set rest duration (default: 10 seconds)
   - Review phase list (can customize)

2. **Storage Targets:**
   - Platform auto-detects NVMe drives
   - Excludes OS drive automatically
   - Filters out small partitions

### 4. Run Test

1. **Start Test:** Click "Start Test" button
2. **Monitor Progress:**
   - Watch real-time charts
   - Monitor metric cards
   - Review log output
3. **Wait for completion:** All phases run automatically

### 5. Generate Reports

1. **Generate Report:** Click "Generate Report" after test completes
2. **Download Report:** Excel file with 7 sheets + charts
3. **Review Data:** CSV exports available for analysis

## Troubleshooting

### Common Issues

#### Platform Won't Start

```bash
# Check Python version
python --version  # Should be 3.10+

# Check dependencies
pip install -r requirements.txt

# Check port availability
netstat -an | grep 8001  # Should be empty
```

#### Connection Failures

```bash
# Test SSH to OS server
ssh <user>@<os-ip>

# Test SSH to iDRAC
ssh root@<idrac-ip>
# Should show racadm>> prompt

# Check network connectivity
ping <os-ip>
ping <idrac-ip>
```

#### Benchmark Failures

```bash
# Check tool availability on server
ssh <user>@<os-ip> "which stress-ng fio bc"

# Check sudo access
ssh <user>@<os-ip> "sudo whoami"

# Check disk mounts
ssh <user>@<os-ip> "df -h | grep nvme"
```

#### iDRAC Issues

```bash
# Test iDRAC access
ssh root@<idrac-ip>
racadm>> rootshell
thmtest -g s

# Check iDRAC version
racadm getversion

# Reset iDRAC SSH service
racadm set iDRAC.SSH.Enable 0
racadm set iDRAC.SSH.Enable 1
```

### Log Locations

**Platform Logs:**
- Console output when running `python run.py`
- Browser developer console for frontend errors

**Server Logs:**
- Benchmark logs available via UI or `/api/test/logs`
- SSH session logs in platform console

**Database Issues:**
- Check `data/platform.db` file permissions
- Verify SQLite database integrity

### Performance Issues

**High Memory Usage:**
- Reduce telemetry collection intervals
- Limit concurrent WebSocket connections
- Clear old test runs from `data/` directory

**Slow Response:**
- Check network latency to target servers
- Verify adequate bandwidth for telemetry
- Consider reducing metric collection frequency

## Backup and Recovery

### Data Backup

```bash
# Backup configuration and run history
tar -czf perf-platform-backup-$(date +%Y%m%d).tar.gz data/

# Backup specific run
tar -czf run-backup-20260302_162939.tar.gz data/20260302_162939/
```

### Recovery

```bash
# Restore from backup
tar -xzf perf-platform-backup-20260302.tar.gz

# Verify database integrity
sqlite3 data/platform.db "PRAGMA integrity_check;"
```

### Migration

To move the platform to another system:

1. **Backup data:** `tar -czf perf-platform-data.tar.gz data/`
2. **Install on new system:** Follow installation steps
3. **Restore data:** `tar -xzf perf-platform-data.tar.gz`
4. **Verify:** Start platform and check configurations

## Security Considerations

### Network Security

- **Firewall:** Restrict access to port 8001 to trusted networks
- **VPN:** Use VPN for remote access when possible
- **SSH Keys:** Use SSH key authentication instead of passwords

### Credential Management

- **Environment Variables:** Store sensitive credentials in environment variables
- **Configuration Files:** Protect `data/platform.db` - contains encrypted passwords
- **Browser Security:** Use HTTPS in production environments

### System Hardening

```bash
# Create dedicated user for platform
sudo useradd -r -s /bin/false perf-platform

# Restrict file permissions
chmod 700 data/
chmod 600 data/platform.db

# Use AppArmor/SELinux (optional)
```

---

*For development setup and contribution guidelines, see the [Developer Guide](development.md).*

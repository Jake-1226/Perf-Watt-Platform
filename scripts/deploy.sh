#!/bin/bash
# Performance Test Platform - VM Deployment Script
# Deploys the full platform onto a development VM with all dependencies

set -euo pipefail

# Configuration
PLATFORM_DIR="/opt/perf-platform"
SERVICE_USER="perf-platform"
PYTHON_VERSION="python3.11"
REPO_URL="${REPO_URL:-https://github.com/your-org/perf-platform.git}"
BRANCH="${BRANCH:-main}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        error "This script must be run as root (use sudo)"
    fi
}

check_system() {
    log "Checking system requirements..."
    
    # Check OS
    if ! command -v apt-get >/dev/null 2>&1; then
        error "This deployment script supports Ubuntu/Debian systems only"
    fi
    
    # Check Python version
    if ! command -v $PYTHON_VERSION >/dev/null 2>&1; then
        log "Installing Python $PYTHON_VERSION..."
        apt-get update -qq
        apt-get install -y software-properties-common
        add-apt-repository ppa:deadsnakes/ppa -y
        apt-get update -qq
        apt-get install -y $PYTHON_VERSION $PYTHON_VERSION-venv $PYTHON_VERSION-pip
    fi
    
    log "System requirements check passed"
}

create_service_user() {
    log "Creating service user: $SERVICE_USER"
    
    if ! id "$SERVICE_USER" >/dev/null 2>&1; then
        useradd -r -s /bin/false -d $PLATFORM_DIR "$SERVICE_USER"
        log "Created user: $SERVICE_USER"
    else
        log "User $SERVICE_USER already exists"
    fi
}

install_dependencies() {
    log "Installing system dependencies..."
    
    apt-get update -qq
    apt-get install -y \
        git \
        curl \
        wget \
        build-essential \
        python3-dev \
        python3-venv \
        sqlite3 \
        nginx \
        supervisor \
        htop \
        iotop \
        netstat-nat
    
    log "System dependencies installed"
}

clone_platform() {
    log "Cloning Performance Test Platform..."
    
    # Remove existing directory if present
    if [[ -d "$PLATFORM_DIR" ]]; then
        warn "Platform directory exists, backing up..."
        mv "$PLATFORM_DIR" "${PLATFORM_DIR}.backup.$(date +%Y%m%d_%H%M%S)"
    fi
    
    # Clone repository
    git clone "$REPO_URL" "$PLATFORM_DIR"
    cd "$PLATFORM_DIR"
    git checkout "$BRANCH"
    
    log "Platform cloned to $PLATFORM_DIR"
}

setup_python_env() {
    log "Setting up Python virtual environment..."
    
    cd "$PLATFORM_DIR"
    
    # Create virtual environment
    $PYTHON_VERSION -m venv venv
    
    # Activate and install dependencies
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    
    log "Python environment setup complete"
}

create_directories() {
    log "Creating platform directories..."
    
    mkdir -p "$PLATFORM_DIR/data"
    mkdir -p "$PLATFORM_DIR/logs"
    mkdir -p "$PLATFORM_DIR/backups"
    
    # Set permissions
    chown -R "$SERVICE_USER:$SERVICE_USER" "$PLATFORM_DIR"
    chmod 755 "$PLATFORM_DIR"
    chmod 755 "$PLATFORM_DIR/data"
    chmod 755 "$PLATFORM_DIR/logs"
    chmod 755 "$PLATFORM_DIR/backups"
    
    log "Directories created and permissions set"
}

setup_systemd_service() {
    log "Setting up systemd service..."
    
    cat > "/etc/systemd/system/perf-platform.service" << EOF
[Unit]
Description=Performance Test Platform
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$PLATFORM_DIR
Environment=PATH=$PLATFORM_DIR/venv/bin
Environment=PYTHONPATH=$PLATFORM_DIR
ExecStart=$PLATFORM_DIR/venv/bin/python run.py --host 0.0.0.0 --port 8001
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable perf-platform
    systemctl start perf-platform
    
    log "Systemd service configured and started"
}

setup_nginx() {
    log "Setting up Nginx reverse proxy..."
    
    cat > "/etc/nginx/sites-available/perf-platform" << EOF
server {
    listen 80;
    server_name _;
    
    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }
    
    location /ws {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }
}
EOF

    # Enable site
    ln -sf /etc/nginx/sites-available/perf-platform /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default
    
    # Test and restart nginx
    nginx -t
    systemctl restart nginx
    systemctl enable nginx
    
    log "Nginx reverse proxy configured"
}

setup_supervisor() {
    log "Setting up Supervisor for process management..."
    
    cat > "/etc/supervisor/conf.d/perf-platform.conf" << EOF
[program:perf-platform]
command=$PLATFORM_DIR/venv/bin/python run.py --host 0.0.0.0 --port 8001
directory=$PLATFORM_DIR
user=$SERVICE_USER
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=$PLATFORM_DIR/logs/perf-platform.log
stderr_logfile=$PLATFORM_DIR/logs/perf-platform.err.log
environment=PATH="$PLATFORM_DIR/venv/bin"
EOF

    supervisorctl reread
    supervisorctl update
    
    log "Supervisor configuration updated"
}

create_health_check() {
    log "Creating health check endpoints..."
    
    cat > "$PLATFORM_DIR/health_check.py" << 'EOF'
#!/usr/bin/env python3
"""Health check script for Performance Test Platform"""
import sys
import sqlite3
import subprocess
from pathlib import Path

def check_service():
    """Check if the main service is running"""
    try:
        result = subprocess.run(['pgrep', '-f', 'python run.py'], 
                              capture_output=True, text=True)
        return result.returncode == 0
    except:
        return False

def check_database():
    """Check if platform database is accessible"""
    try:
        db_path = Path('/opt/perf-platform/data/platform.db')
        if not db_path.exists():
            return False
        conn = sqlite3.connect(str(db_path))
        conn.execute("SELECT 1 FROM sqlite_master LIMIT 1")
        conn.close()
        return True
    except:
        return False

def check_port():
    """Check if the service port is listening"""
    try:
        result = subprocess.run(['netstat', '-ln'], 
                              capture_output=True, text=True)
        return ':8001' in result.stdout
    except:
        return False

def main():
    checks = {
        'service': check_service(),
        'database': check_database(),
        'port': check_port()
    }
    
    all_passed = all(checks.values())
    
    if all_passed:
        print("HEALTHY")
        sys.exit(0)
    else:
        print("UNHEALTHY")
        for name, status in checks.items():
            if not status:
                print(f"  {name}: FAILED")
        sys.exit(1)

if __name__ == '__main__':
    main()
EOF

    chmod +x "$PLATFORM_DIR/health_check.py"
    chown "$SERVICE_USER:$SERVICE_USER" "$PLATFORM_DIR/health_check.py"
    
    log "Health check script created"
}

create_cli_tool() {
    log "Creating CLI tool for remote triggering..."
    
    cat > "$PLATFORM_DIR/cli.py" << 'EOF'
#!/usr/bin/env python3
"""CLI tool for Performance Test Platform"""
import argparse
import json
import sys
import requests
from pathlib import Path

def run_test(server_url, config_file=None, phase_duration=30, rest_duration=10):
    """Run a test via API"""
    
    # Load configuration
    config = {}
    if config_file and Path(config_file).exists():
        with open(config_file) as f:
            config = json.load(f)
    
    # Default configuration
    default_config = {
        "phase_duration": phase_duration,
        "rest_duration": rest_duration,
        "phases": [
            {"name": "01_idle_baseline", "type": "idle", "duration": max(phase_duration // 3, 10)},
            {"name": "02_hpl_100pct", "type": "hpl_100", "duration": phase_duration},
            {"name": "03_hpl_50pct", "type": "hpl_50", "duration": phase_duration},
            {"name": "04_fio_100pct", "type": "fio_100", "duration": phase_duration},
            {"name": "05_fio_50pct", "type": "fio_50", "duration": phase_duration},
            {"name": "06_hpl_fio_100pct", "type": "hpl_fio_100", "duration": phase_duration},
            {"name": "07_hpl_fio_50pct", "type": "hpl_fio_50", "duration": phase_duration},
            {"name": "08_idle_cooldown", "type": "idle", "duration": max(phase_duration // 3, 10)}
        ]
    }
    
    # Merge with provided config
    test_config = {**default_config, **config}
    
    try:
        # Start test
        response = requests.post(f"{server_url}/api/test/start", 
                                json=test_config, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        print(f"Test started successfully!")
        print(f"Run ID: {result.get('run_id')}")
        print(f"Status: {result.get('status')}")
        
        return result.get('run_id')
        
    except requests.exceptions.RequestException as e:
        print(f"Error starting test: {e}")
        sys.exit(1)

def get_status(server_url):
    """Get current test status"""
    try:
        response = requests.get(f"{server_url}/api/test/status", timeout=10)
        response.raise_for_status()
        
        status = response.json()
        print(f"Running: {status.get('running')}")
        print(f"Phase: {status.get('current_phase')}")
        print(f"Run ID: {status.get('run_id')}")
        print(f"Log lines: {status.get('log_lines')}")
        
    except requests.exceptions.RequestException as e:
        print(f"Error getting status: {e}")
        sys.exit(1)

def stop_test(server_url):
    """Stop current test"""
    try:
        response = requests.post(f"{server_url}/api/test/stop", timeout=10)
        response.raise_for_status()
        
        result = response.json()
        print(f"Test stopped: {result.get('status')}")
        
    except requests.exceptions.RequestException as e:
        print(f"Error stopping test: {e}")
        sys.exit(1)

def generate_report(server_url):
    """Generate test report"""
    try:
        response = requests.post(f"{server_url}/api/report/generate", timeout=30)
        response.raise_for_status()
        
        result = response.json()
        print(f"Report generated: {result.get('status')}")
        print(f"Run ID: {result.get('run_id')}")
        
    except requests.exceptions.RequestException as e:
        print(f"Error generating report: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description='Performance Test Platform CLI')
    parser.add_argument('--server', default='http://localhost:8001', 
                       help='Platform server URL')
    parser.add_argument('--config', help='Configuration file (JSON)')
    parser.add_argument('--phase-duration', type=int, default=30,
                       help='Phase duration in seconds')
    parser.add_argument('--rest-duration', type=int, default=10,
                       help='Rest duration in seconds')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Run command
    run_parser = subparsers.add_parser('run', help='Run a test')
    run_parser.add_argument('--quick', action='store_true',
                          help='Run quick test (15s phases)')
    
    # Status command
    subparsers.add_parser('status', help='Get test status')
    
    # Stop command
    subparsers.add_parser('stop', help='Stop current test')
    
    # Report command
    subparsers.add_parser('report', help='Generate report')
    
    args = parser.parse_args()
    
    if args.command == 'run':
        if args.quick:
            run_test(args.server, args.config, 15, 5)
        else:
            run_test(args.server, args.config, args.phase_duration, args.rest_duration)
    elif args.command == 'status':
        get_status(args.server)
    elif args.command == 'stop':
        stop_test(args.server)
    elif args.command == 'report':
        generate_report(args.server)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
EOF

    chmod +x "$PLATFORM_DIR/cli.py"
    chown "$SERVICE_USER:$SERVICE_USER" "$PLATFORM_DIR/cli.py"
    
    log "CLI tool created"
}

create_automation_scripts() {
    log "Creating automation scripts..."
    
    # Automated test script
    cat > "$PLATFORM_DIR/scripts/run_automated_test.sh" << 'EOF'
#!/bin/bash
# Automated end-to-end test script

set -euo pipefail

PLATFORM_URL="${PLATFORM_URL:-http://localhost:8001}"
CONFIG_FILE="${CONFIG_FILE:-}"
PHASE_DURATION="${PHASE_DURATION:-30}"
REST_DURATION="${REST_DURATION:-10}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Run health check
log "Running health check..."
/opt/perf-platform/health_check.py

# Connect to server (if config provided)
if [[ -n "$CONFIG_FILE" ]]; then
    log "Connecting to server..."
    curl -X POST "$PLATFORM_URL/api/connect" \
         -H "Content-Type: application/json" \
         -d "@$CONFIG_FILE"
fi

# Run sanity check
log "Running sanity check..."
curl -X POST "$PLATFORM_URL/api/sanity_check"

# Start test
log "Starting automated test..."
RUN_ID=$(/opt/perf-platform/cli.py --server "$PLATFORM_URL" run \
          --phase-duration "$PHASE_DURATION" \
          --rest-duration "$REST_DURATION" \
          --config "$CONFIG_FILE" 2>/dev/null | grep "Run ID:" | cut -d' ' -f3)

if [[ -n "$RUN_ID" ]]; then
    log "Test started with ID: $RUN_ID"
    
    # Monitor test progress
    while true; do
        STATUS=$(/opt/perf-platform/cli.py --server "$PLATFORM_URL" status 2>/dev/null)
        RUNNING=$(echo "$STATUS" | grep "Running:" | cut -d' ' -f2)
        
        if [[ "$RUNNING" == "False" ]]; then
            log "Test completed"
            break
        fi
        
        PHASE=$(echo "$STATUS" | grep "Phase:" | cut -d' ' -f2)
        log "Current phase: $PHASE"
        
        sleep 10
    done
    
    # Generate report
    log "Generating report..."
    /opt/perf-platform/cli.py --server "$PLATFORM_URL" report
    
    log "Automated test completed successfully"
else
    log "ERROR: Failed to start test"
    exit 1
fi
EOF

    chmod +x "$PLATFORM_DIR/scripts/run_automated_test.sh"
    chown "$SERVICE_USER:$SERVICE_USER" "$PLATFORM_DIR/scripts/run_automated_test.sh"
    
    # Scheduler script (cron example)
    cat > "$PLATFORM_DIR/scripts/scheduler_example.sh" << 'EOF'
#!/bin/bash
# Example scheduler script (can be used with cron)

# Add to crontab for scheduled runs:
# 0 2 * * * /opt/perf-platform/scripts/scheduler_example.sh

PLATFORM_URL="http://localhost:8001"
CONFIG_FILE="/opt/perf-platform/configs/production.json"
LOG_FILE="/opt/perf-platform/logs/scheduled_$(date +%Y%m%d).log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "Starting scheduled test..."

# Run the automated test
/opt/perf-platform/scripts/run_automated_test.sh >> "$LOG_FILE" 2>&1

log "Scheduled test completed"
EOF

    chmod +x "$PLATFORM_DIR/scripts/scheduler_example.sh"
    chown "$SERVICE_USER:$SERVICE_USER" "$PLATFORM_DIR/scripts/scheduler_example.sh"
    
    log "Automation scripts created"
}

verify_deployment() {
    log "Verifying deployment..."
    
    # Check service status
    if systemctl is-active --quiet perf-platform; then
        log "✓ Service is running"
    else
        error "Service is not running"
    fi
    
    # Check port accessibility
    if netstat -ln | grep -q ':8001'; then
        log "✓ Port 8001 is listening"
    else
        error "Port 8001 is not listening"
    fi
    
    # Check health endpoint
    if "$PLATFORM_DIR/health_check.py" >/dev/null 2>&1; then
        log "✓ Health check passed"
    else
        error "Health check failed"
    fi
    
    # Test API
    if curl -s "http://localhost:8001/api/configs" >/dev/null; then
        log "✓ API is responding"
    else
        error "API is not responding"
    fi
    
    log "Deployment verification completed successfully"
}

main() {
    log "Starting Performance Test Platform deployment..."
    
    check_root
    check_system
    create_service_user
    install_dependencies
    clone_platform
    setup_python_env
    create_directories
    setup_systemd_service
    setup_nginx
    setup_supervisor
    create_health_check
    create_cli_tool
    create_automation_scripts
    verify_deployment
    
    log "Deployment completed successfully!"
    log ""
    log "Platform is available at: http://$(hostname -I | cut -d' ' -f1):8001"
    log "CLI tool: $PLATFORM_DIR/cli.py"
    log "Health check: $PLATFORM_DIR/health_check.py"
    log "Automated test: $PLATFORM_DIR/scripts/run_automated_test.sh"
    log ""
    log "To run a test:"
    log "  $PLATFORM_DIR/cli.py run"
    log ""
    log "To check status:"
    log "  $PLATFORM_DIR/cli.py status"
    log ""
    log "To run automated test:"
    log "  $PLATFORM_DIR/scripts/run_automated_test.sh"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
EOF

    chmod +x "$PLATFORM_DIR/scripts/deploy.sh"
    
    log "Deployment script created: $PLATFORM_DIR/scripts/deploy.sh"

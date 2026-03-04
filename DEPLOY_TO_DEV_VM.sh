#!/bin/bash
# Complete Deployment Script for Dev VM
# Target: 10.244.236.154 (root user)

set -euo pipefail

# Configuration
VM_IP="10.244.236.154"
VM_USER="root"
PLATFORM_DIR="/opt/perf-platform"
LOCAL_DIR="c:/Users/ManuNicholas_Jacob/CascadeProjects/windsurf-project/perf-platform"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

info() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')] INFO: $1${NC}"
}

# Test SSH connection
test_ssh_connection() {
    log "Testing SSH connection to $VM_IP..."
    if ! ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 "$VM_USER@$VM_IP" "echo 'SSH connection successful'" 2>/dev/null; then
        error "Cannot connect to VM at $VM_IP with user $VM_USER"
    fi
    log "✅ SSH connection successful"
}

# Copy files to VM
copy_files_to_vm() {
    log "Copying platform files to VM..."
    
    # Create remote directory
    ssh -o StrictHostKeyChecking=no "$VM_USER@$VM_IP" "mkdir -p $PLATFORM_DIR"
    
    # Copy all files using SCP
    info "Copying platform directory..."
    scp -o StrictHostKeyChecking=no -r "$LOCAL_DIR"/* "$VM_USER@$VM_IP:$PLATFORM_DIR/"
    
    log "✅ Files copied to VM"
}

# Run deployment on VM
run_remote_deployment() {
    log "Running deployment on VM..."
    
    ssh -o StrictHostKeyChecking=no "$VM_USER@$VM_IP" << 'EOF'
set -euo pipefail

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date '+%H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[$(date '+%H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

warn() {
    echo -e "${YELLOW}[$(date '+%H:%M:%S')] WARNING: $1${NC}"
}

echo "=== Starting Remote Deployment ==="
echo "Platform Dir: /opt/perf-platform"
echo ""

# Update system
log "Updating system packages..."
apt-get update -qq

# Install dependencies
log "Installing dependencies..."
apt-get install -y \
    git \
    curl \
    wget \
    build-essential \
    python3-dev \
    python3-venv \
    python3-pip \
    sqlite3 \
    nginx \
    supervisor \
    htop \
    netstat-nat \
    ufw \
    expect

# Create service user
log "Creating service user..."
if ! id perf-platform >/dev/null 2>&1; then
    useradd -r -s /bin/bash -d /opt/perf-platform perf-platform
    log "Created user: perf-platform"
else
    log "User perf-platform already exists"
fi

# Create directories
log "Creating directories..."
mkdir -p /opt/perf-platform/{data,logs,configs,scripts}
chown -R perf-platform:perf-platform /opt/perf-platform
chmod 755 /opt/perf-platform

# Setup Python environment
log "Setting up Python environment..."
cd /opt/perf-platform
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip

# Install requirements
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    # Install basic requirements if file doesn't exist
    pip install fastapi uvicorn[standard] websockets python-multipart pydantic paramiko openpyxl
fi

# Create systemd service
log "Creating systemd service..."
cat > /etc/systemd/system/perf-platform.service << 'EOFSVC'
[Unit]
Description=Performance Test Platform
After=network.target

[Service]
Type=simple
User=perf-platform
Group=perf-platform
WorkingDirectory=/opt/perf-platform
Environment=PATH=/opt/perf-platform/venv/bin
Environment=PYTHONPATH=/opt/perf-platform
ExecStart=/opt/perf-platform/venv/bin/python run.py --host 0.0.0.0 --port 8001
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOFSVC

# Configure nginx
log "Configuring nginx..."
cat > /etc/nginx/sites-available/perf-platform << 'EOFNGINX'
server {
    listen 80;
    server_name _;
    
    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }
    
    location /ws {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }
}
EOFNGINX

# Enable nginx site
ln -sf /etc/nginx/sites-available/perf-platform /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Configure firewall
log "Configuring firewall..."
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 8001/tcp
ufw --force enable

# Start services
log "Starting services..."
systemctl daemon-reload
systemctl enable perf-platform
systemctl start perf-platform
systemctl restart nginx
systemctl enable nginx

# Wait for service to start
log "Waiting for service to start..."
sleep 15

# Create health check script
log "Creating health check script..."
cat > /opt/perf-platform/health_check.py << 'EOFHEALTH'
#!/usr/bin/env python3
import subprocess
import sys
import sqlite3
from pathlib import Path

def check_service():
    try:
        result = subprocess.run(['pgrep', '-f', 'python run.py'], capture_output=True, text=True)
        return result.returncode == 0
    except:
        return False

def check_database():
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
    try:
        result = subprocess.run(['netstat', '-ln'], capture_output=True, text=True)
        return ':8001' in result.stdout
    except:
        return False

def check_dependencies():
    try:
        import fastapi
        import uvicorn
        import paramiko
        import websockets
        import openpyxl
        return True
    except ImportError as e:
        print(f"Missing dependency: {e}")
        return False

def main():
    checks = {
        'service': check_service(),
        'database': check_database(),
        'port': check_port(),
        'dependencies': check_dependencies()
    }
    
    all_passed = all(checks.values())
    
    if all_passed:
        print("HEALTHY")
        print("All health checks passed")
        sys.exit(0)
    else:
        print("UNHEALTHY")
        failed_checks = [name for name, status in checks.items() if not status]
        for name in failed_checks:
            print(f"  {name}: FAILED")
        sys.exit(1)

if __name__ == '__main__':
    main()
EOFHEALTH

chmod +x /opt/perf-platform/health_check.py
chown perf-platform:perf-platform /opt/perf-platform/health_check.py

# Create CLI tool
log "Creating CLI tool..."
cat > /opt/perf-platform/cli.py << 'EOFCLI'
#!/usr/bin/env python3
import argparse
import requests
import sys
import json

class PerfPlatformCLI:
    def __init__(self, server_url="http://localhost:8001"):
        self.server_url = server_url
        self.session = requests.Session()
        self.session.timeout = 30

    def _request(self, method, endpoint, data=None, json_data=None):
        try:
            url = f"{self.server_url}{endpoint}"
            if method == 'GET':
                response = self.session.get(url)
            elif method == 'POST':
                if json_data:
                    response = self.session.post(url, json=json_data)
                else:
                    response = self.session.post(url, data=data)
            elif method == 'DELETE':
                response = self.session.delete(url)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error: {e}")
            sys.exit(1)

    def health_check(self):
        try:
            response = self.session.get(f"{self.server_url}/api/configs", timeout=10)
            if response.status_code == 200:
                print("✓ Platform is healthy")
                return True
            else:
                print("✗ Platform API not responding")
                return False
        except Exception as e:
            print(f"✗ Health check failed: {e}")
            return False

    def status(self):
        try:
            response = self.session.get(f"{self.server_url}/api/test/status", timeout=10)
            if response.status_code == 200:
                status = response.json()
                print(f"Running: {status.get('running')}")
                print(f"Phase: {status.get('current_phase')}")
                print(f"Run ID: {status.get('run_id')}")
                return status
            else:
                print("✗ Status check failed")
                return None
        except Exception as e:
            print(f"✗ Status check failed: {e}")
            return None

def main():
    parser = argparse.ArgumentParser(description='Performance Test Platform CLI')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    subparsers.add_parser('health', help='Perform health check')
    subparsers.add_parser('status', help='Get test status')
    
    args = parser.parse_args()
    
    cli = PerfPlatformCLI()
    
    if args.command == 'health':
        cli.health_check()
    elif args.command == 'status':
        cli.status()
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
EOFCLI

chmod +x /opt/perf-platform/cli.py
chown perf-platform:perf-platform /opt/perf-platform/cli.py

# Create quick test script
log "Creating quick test script..."
cat > /opt/perf-platform/scripts/quick_test.sh << 'EOFQUICK'
#!/bin/bash
echo "=== Performance Test Platform Quick Test ==="
echo ""

# Check service status
echo "1. Checking service status..."
if systemctl is-active --quiet perf-platform; then
    echo "✓ Platform service is running"
else
    echo "✗ Platform service is not running"
    exit 1
fi

# Check API
echo "2. Checking API..."
if curl -s http://localhost:8001/api/configs >/dev/null; then
    echo "✓ API is responding"
else
    echo "✗ API is not responding"
    exit 1
fi

# Check health
echo "3. Checking health..."
if /opt/perf-platform/health_check.py >/dev/null 2>&1; then
    echo "✓ Health check passed"
else
    echo "✗ Health check failed"
    exit 1
fi

# Check CLI
echo "4. Testing CLI tool..."
if /opt/perf-platform/cli.py health >/dev/null 2>&1; then
    echo "✓ CLI tool is working"
else
    echo "✗ CLI tool failed"
    exit 1
fi

echo ""
echo "=== All Tests Passed ==="
echo "Platform is ready for use!"
echo ""
echo "Access Information:"
echo "  Web UI: http://$(hostname -I | cut -d' ' -f1):8001"
echo "  API: http://$(hostname -I | cut -d' ' -f1):8001/api/"
echo "  Health: http://$(hostname -I | cut -d' ' -f1):8001/health"
echo ""
echo "Next Steps:"
echo "  1. Configure target server in /opt/perf-platform/configs/"
echo "  2. Access web UI to run tests"
echo "  3. Use CLI tool: /opt/perf-platform/cli.py"
EOFQUICK

chmod +x /opt/perf-platform/scripts/quick_test.sh
chown perf-platform:perf-platform /opt/perf-platform/scripts/quick_test.sh

# Create test configuration
log "Creating test configuration..."
cat > /opt/perf-platform/configs/test_server.json << 'EOFCONFIG'
{
  "name": "Test Server",
  "os_ip": "192.168.1.100",
  "os_user": "dell",
  "os_pass": "calvin",
  "idrac_ip": "192.168.1.101",
  "idrac_user": "root",
  "idrac_pass": "calvin",
  "notes": "Test configuration - update with your actual server details"
}
EOFCONFIG

# Verify deployment
log "Verifying deployment..."
if systemctl is-active --quiet perf-platform && \
   curl -s http://localhost:8001/api/configs >/dev/null && \
   /opt/perf-platform/health_check.py >/dev/null 2>&1; then
    log "✅ Deployment verification passed"
else
    error "❌ Deployment verification failed"
fi

# Run quick test
log "Running quick test..."
/opt/perf-platform/scripts/quick_test.sh

log "🎉 Remote deployment completed successfully!"
echo ""
echo "=== Access Information ==="
echo "Web UI: http://$(hostname -I | cut -d' ' -f1):8001"
echo "API: http://$(hostname -I | cut -d' ' -f1):8001/api/"
echo "Health: http://$(hostname -I | cut -d' ' -f1):8001/health"
echo ""
echo "=== Quick Commands ==="
echo "Check status: systemctl status perf-platform"
echo "View logs: journalctl -u perf-platform -f"
echo "Run test: /opt/perf-platform/scripts/quick_test.sh"
echo "CLI tool: /opt/perf-platform/cli.py"
echo ""
echo "=== Next Steps ==="
echo "1. Edit target server config: nano /opt/perf-platform/configs/test_server.json"
echo "2. Access web UI to configure and run tests"
echo "3. Use CLI tool for automation: /opt/perf-platform/cli.py"

EOF

    log "✅ Remote deployment completed"
}

# Verify deployment
verify_deployment() {
    log "Verifying deployment on VM..."
    
    # Check service status
    SERVICE_STATUS=$(ssh -o StrictHostKeyChecking=no "$VM_USER@$VM_IP" "systemctl is-active perf-platform")
    if [[ "$SERVICE_STATUS" != "active" ]]; then
        error "Platform service is not running: $SERVICE_STATUS"
    fi
    
    # Check API accessibility
    if ! ssh -o StrictHostKeyChecking=no "$VM_USER@$VM_IP" "curl -s http://localhost:8001/api/configs >/dev/null"; then
        error "API is not responding"
    fi
    
    # Check health
    if ! ssh -o StrictHostKeyChecking=no "$VM_USER@$VM_IP" "/opt/perf-platform/health_check.py" >/dev/null 2>&1; then
        error "Health check failed"
    fi
    
    log "✅ Deployment verification passed"
}

# Display access information
display_access_info() {
    log "🎉 Deployment completed successfully!"
    echo ""
    echo "=== Access Information ==="
    echo "VM IP: $VM_IP"
    echo "Web UI: http://$VM_IP:8001"
    echo "API: http://$VM_IP:8001/api/"
    echo "Health: http://$VM_IP:8001/health"
    echo ""
    echo "=== Quick Commands ==="
    echo "Check status: ssh $VM_USER@$VM_IP 'systemctl status perf-platform'"
    echo "View logs: ssh $VM_USER@$VM_IP 'journalctl -u perf-platform -f'"
    echo "Run test: ssh $VM_USER@$VM_IP '/opt/perf-platform/scripts/quick_test.sh'"
    echo "CLI tool: ssh $VM_USER@$VM_IP '/opt/perf-platform/cli.py'"
    echo ""
    echo "=== Next Steps ==="
    echo "1. Access web UI: http://$VM_IP:8001"
    echo "2. Configure target server in web interface"
    echo "3. Run your first test"
    echo "4. Monitor results in real-time"
}

# Main execution
main() {
    echo "=== Performance Test Platform Deployment to Dev VM ==="
    echo "Target VM: $VM_IP"
    echo "User: $VM_USER"
    echo "Local Dir: $LOCAL_DIR"
    echo "Remote Dir: $PLATFORM_DIR"
    echo ""
    
    test_ssh_connection
    copy_files_to_vm
    run_remote_deployment
    verify_deployment
    display_access_info
    
    log "🚀 Deployment completed successfully!"
    echo ""
    echo "Your Performance Test Platform is now running on the dev VM!"
    echo "Access it at: http://$VM_IP:8001"
}

# Run main function
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi

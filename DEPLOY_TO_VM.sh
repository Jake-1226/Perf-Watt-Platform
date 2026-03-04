#!/bin/bash
# Complete VM Deployment Script for Performance Test Platform
# This script deploys the entire platform to a VM for immediate testing

set -euo pipefail

# Configuration
PLATFORM_DIR="/opt/perf-platform"
SERVICE_USER="perf-platform"
PYTHON_VERSION="python3.11"
REPO_URL="${REPO_URL:-https://github.com/your-org/perf-platform.git}"
BRANCH="${BRANCH:-main}"
VM_IP="${VM_IP:-localhost}"
SSH_USER="${SSH_USER:-root}"
SSH_KEY="${SSH_KEY:-}"

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

# SSH function for remote execution
ssh_exec() {
    local cmd="$1"
    if [[ -n "$SSH_KEY" ]]; then
        ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$SSH_USER@$VM_IP" "$cmd"
    else
        ssh -o StrictHostKeyChecking=no "$SSH_USER@$VM_IP" "$cmd"
    fi
}

# Copy files to VM
scp_to_vm() {
    local src="$1"
    local dst="$2"
    if [[ -n "$SSH_KEY" ]]; then
        scp -i "$SSH_KEY" -o StrictHostKeyChecking=no -r "$src" "$SSH_USER@$VM_IP:$dst"
    else
        scp -o StrictHostKeyChecking=no -r "$src" "$SSH_USER@$VM_IP:$dst"
    fi
}

check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check if we can connect to VM
    if ! ssh_exec "echo 'SSH connection successful'"; then
        error "Cannot connect to VM at $VM_IP with user $SSH_USER"
    fi
    
    # Check VM OS
    OS_INFO=$(ssh_exec "cat /etc/os-release | grep '^ID=' | cut -d'=' -f2 | tr -d '\"'")
    if [[ "$OS_INFO" != "ubuntu" && "$OS_INFO" != "debian" ]]; then
        warn "VM OS is $OS_INFO (Ubuntu/Debian recommended)"
    fi
    
    log "Prerequisites check passed"
}

prepare_vm() {
    log "Preparing VM for deployment..."
    
    # Update system
    ssh_exec "apt-get update -qq"
    
    # Install required packages
    ssh_exec "apt-get install -y \
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
        iotop \
        netstat-nat \
        ufw"
    
    # Create service user
    ssh_exec "if ! id '$SERVICE_USER' >/dev/null 2>&1; then \
        useradd -r -s /bin/bash -d '$PLATFORM_DIR' '$SERVICE_USER'; \
    fi"
    
    # Create directories
    ssh_exec "mkdir -p '$PLATFORM_DIR' '$PLATFORM_DIR/data' '$PLATFORM_DIR/logs' '$PLATFORM_DIR/configs' '$PLATFORM_DIR/scripts'"
    
    # Set permissions
    ssh_exec "chown -R '$SERVICE_USER:$SERVICE_USER' '$PLATFORM_DIR'"
    ssh_exec "chmod 755 '$PLATFORM_DIR'"
    
    log "VM preparation completed"
}

deploy_platform() {
    log "Deploying Performance Test Platform to VM..."
    
    # Create temporary directory on VM
    ssh_exec "mkdir -p /tmp/perf-platform-deploy"
    
    # Copy platform files to VM
    info "Copying platform files to VM..."
    scp_to_vm "." "/tmp/perf-platform-deploy/"
    
    # Move files to final location
    ssh_exec "mv /tmp/perf-platform-deploy/* '$PLATFORM_DIR/'"
    ssh_exec "rmdir /tmp/perf-platform-deploy"
    
    # Set ownership
    ssh_exec "chown -R '$SERVICE_USER:$SERVICE_USER' '$PLATFORM_DIR'"
    
    log "Platform files deployed"
}

setup_python_environment() {
    log "Setting up Python environment..."
    
    ssh_exec "cd '$PLATFORM_DIR' && \
        '$PYTHON_VERSION' -m venv venv && \
        source venv/bin/activate && \
        pip install --upgrade pip && \
        pip install -r requirements.txt"
    
    log "Python environment setup completed"
}

configure_services() {
    log "Configuring system services..."
    
    # Create systemd service
    ssh_exec "cat > /etc/systemd/system/perf-platform.service << 'EOF'
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
EOF"
    
    # Configure nginx
    ssh_exec "cat > /etc/nginx/sites-available/perf-platform << 'EOF'
server {
    listen 80;
    server_name _;
    
    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection \"upgrade\";
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
        proxy_set_header Connection \"upgrade\";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }
}
EOF"
    
    # Enable nginx site
    ssh_exec "ln -sf /etc/nginx/sites-available/perf-platform /etc/nginx/sites-enabled/"
    ssh_exec "rm -f /etc/nginx/sites-enabled/default"
    
    # Configure firewall
    ssh_exec "ufw allow 22/tcp"
    ssh_exec "ufw allow 80/tcp"
    ssh_exec "ufw allow 8001/tcp"
    ssh_exec "ufw --force enable"
    
    log "Services configured"
}

start_services() {
    log "Starting services..."
    
    # Reload and start services
    ssh_exec "systemctl daemon-reload"
    ssh_exec "systemctl enable perf-platform"
    ssh_exec "systemctl start perf-platform"
    ssh_exec "systemctl restart nginx"
    ssh_exec "systemctl enable nginx"
    
    log "Services started"
}

verify_deployment() {
    log "Verifying deployment..."
    
    # Wait for service to start
    sleep 10
    
    # Check service status
    SERVICE_STATUS=$(ssh_exec "systemctl is-active perf-platform")
    if [[ "$SERVICE_STATUS" != "active" ]]; then
        error "Platform service is not running: $SERVICE_STATUS"
    fi
    
    # Check port accessibility
    if ! ssh_exec "netstat -ln | grep ':8001'"; then
        error "Port 8001 is not listening"
    fi
    
    # Check API accessibility
    if ! ssh_exec "curl -s http://localhost:8001/api/configs >/dev/null"; then
        error "API is not responding"
    fi
    
    # Check nginx
    if ! ssh_exec "systemctl is-active nginx"; then
        warn "Nginx is not running"
    fi
    
    log "Deployment verification passed"
}

create_test_configuration() {
    log "Creating test configuration..."
    
    # Create example configuration
    ssh_exec "cat > '$PLATFORM_DIR/configs/test_server.json' << 'EOF'
{
  "name": "Test Server",
  "os_ip": "TARGET_SERVER_IP",
  "os_user": "dell",
  "os_pass": "calvin",
  "idrac_ip": "TARGET_IDRAC_IP",
  "idrac_user": "root",
  "idrac_pass": "calvin",
  "notes": "Test configuration for VM deployment"
}
EOF"
    
    # Create quick test script
    ssh_exec "cat > '$PLATFORM_DIR/scripts/quick_test.sh' << 'EOF'
#!/bin/bash
# Quick test script for VM deployment

set -euo pipefail

PLATFORM_DIR="/opt/perf-platform"
SERVER_URL="http://localhost:8001"

echo "=== Performance Test Platform Quick Test ==="
echo "Server URL: $SERVER_URL"
echo "Platform Dir: $PLATFORM_DIR"
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
if curl -s "$SERVER_URL/api/configs" >/dev/null; then
    echo "✓ API is responding"
else
    echo "✗ API is not responding"
    exit 1
fi

# Check health
echo "3. Checking health..."
if "$PLATFORM_DIR/health_check.py" >/dev/null 2>&1; then
    echo "✓ Health check passed"
else
    echo "✗ Health check failed"
    exit 1
fi

# Test CLI
echo "4. Testing CLI tool..."
if "$PLATFORM_DIR/cli.py" health >/dev/null 2>&1; then
    echo "✓ CLI tool is working"
else
    echo "✗ CLI tool failed"
    exit 1
fi

echo ""
echo "=== All Tests Passed ==="
echo "Platform is ready for use!"
echo ""
echo "Next steps:"
echo "1. Configure target server: Edit $PLATFORM_DIR/configs/test_server.json"
echo "2. Access web UI: http://$(hostname -I | cut -d' ' -f1):8001"
echo "3. Run quick test: $PLATFORM_DIR/scripts/quick_test.sh"
echo "4. Run automated test: $PLATFORM_DIR/scripts/run_automated_test.sh --quick"
EOF"
    
    ssh_exec "chmod +x '$PLATFORM_DIR/scripts/quick_test.sh'"
    ssh_exec "chown '$SERVICE_USER:$SERVICE_USER' '$PLATFORM_DIR/scripts/quick_test.sh'"
    
    log "Test configuration created"
}

display_access_info() {
    log "Deployment completed successfully!"
    echo ""
    echo "=== Access Information ==="
    echo "VM IP: $VM_IP"
    echo "Web UI: http://$VM_IP"
    echo "API: http://$VM_IP:8001/api/"
    echo "Health: http://$VM_IP:8001/health"
    echo ""
    echo "=== Quick Commands ==="
    echo "Check status: ssh $SSH_USER@$VM_IP 'systemctl status perf-platform'"
    echo "View logs: ssh $SSH_USER@$VM_IP 'journalctl -u perf-platform -f'"
    echo "Run test: ssh $SSH_USER@$VM_IP '$PLATFORM_DIR/scripts/quick_test.sh'"
    echo ""
    echo "=== Configuration Files ==="
    echo "Platform config: $PLATFORM_DIR/configs/test_server.json"
    echo "CLI tool: $PLATFORM_DIR/cli.py"
    echo "Automated test: $PLATFORM_DIR/scripts/run_automated_test.sh"
    echo ""
    echo "=== Next Steps ==="
    echo "1. Edit the test configuration with your target server details"
    echo "2. Run the quick test to verify everything works"
    echo "3. Start testing with your actual target servers"
}

main() {
    echo "=== Performance Test Platform VM Deployment ==="
    echo "Target VM: $VM_IP"
    echo "SSH User: $SSH_USER"
    echo "Platform Dir: $PLATFORM_DIR"
    echo ""
    
    check_prerequisites
    prepare_vm
    deploy_platform
    setup_python_environment
    configure_services
    start_services
    verify_deployment
    create_test_configuration
    display_access_info
    
    log "VM deployment completed successfully!"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --vm-ip)
            VM_IP="$2"
            shift 2
            ;;
        --ssh-user)
            SSH_USER="$2"
            shift 2
            ;;
        --ssh-key)
            SSH_KEY="$2"
            shift 2
            ;;
        --repo-url)
            REPO_URL="$2"
            shift 2
            ;;
        --branch)
            BRANCH="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --vm-ip IP           Target VM IP address (default: localhost)"
            echo "  --ssh-user USER      SSH user (default: root)"
            echo "  --ssh-key FILE      SSH private key file"
            echo "  --repo-url URL      Repository URL"
            echo "  --branch BRANCH     Git branch (default: main)"
            echo "  --help, -h          Show this help"
            exit 0
            ;;
        *)
            error "Unknown option: $1"
            ;;
    esac
done

# Run main function
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi

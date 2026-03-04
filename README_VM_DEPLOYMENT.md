# VM Deployment Instructions

## Quick Start - Deploy to VM

### Option 1: Automated Deployment (Recommended)

1. **Copy files to VM** (using SCP or similar):
```bash
# Copy the entire platform directory to your VM
scp -r perf-platform/ root@<VM_IP>:/opt/
```

2. **Run deployment script on VM**:
```bash
# SSH to VM
ssh root@<VM_IP>

# Navigate to platform directory
cd /opt/perf-platform

# Make deployment script executable
chmod +x DEPLOY_TO_VM.sh

# Run deployment
./DEPLOY_TO_VM.sh --vm-ip <VM_IP> --ssh-user root
```

### Option 2: Manual Deployment

1. **SSH to VM**:
```bash
ssh root@<VM_IP>
```

2. **Run the pre-built deployment script**:
```bash
# Download and run
curl -fsSL https://raw.githubusercontent.com/your-org/perf-platform/main/scripts/deploy.sh | bash
```

## What the Deployment Does

The deployment script automatically:

✅ **System Preparation**
- Updates package lists
- Installs required dependencies (Python, nginx, etc.)
- Creates service user account
- Sets up directories and permissions

✅ **Platform Installation**
- Deploys all platform files to `/opt/perf-platform/`
- Sets up Python virtual environment
- Installs Python dependencies
- Configures systemd service

✅ **Web Server Setup**
- Configures nginx reverse proxy
- Sets up firewall rules
- Enables SSL-ready configuration

✅ **Service Management**
- Creates systemd service for auto-start
- Enables and starts all services
- Sets up log rotation

✅ **Testing Setup**
- Creates test configuration files
- Sets up quick test scripts
- Verifies deployment

## Post-Deployment Testing

Once deployment is complete, run these tests:

### 1. Quick Health Check
```bash
/opt/perf-platform/scripts/quick_test.sh
```

### 2. Access Web Interface
Open browser: `http://<VM_IP>`

### 3. Test CLI Tool
```bash
/opt/perf-platform/cli.py health
```

### 4. Test API
```bash
curl http://localhost:8001/api/configs
```

## Configuration

### Edit Target Server Configuration
```bash
nano /opt/perf-platform/configs/test_server.json
```

Replace with your actual server details:
```json
{
  "name": "Target Server",
  "os_ip": "192.168.1.100",
  "os_user": "dell", 
  "os_pass": "calvin",
  "idrac_ip": "192.168.1.101",
  "idrac_user": "root",
  "idrac_pass": "calvin"
}
```

### Run First Test
```bash
# Quick test (simulated)
/opt/perf-platform/scripts/run_automated_test.sh --quick

# Or with actual target
/opt/perf-platform/scripts/run_automated_test.sh \
  --config /opt/perf-platform/configs/test_server.json
```

## Access Information

After deployment, you can access:

- **Web UI**: `http://<VM_IP>`
- **API**: `http://<VM_IP>:8001/api/`
- **Health Check**: `http://<VM_IP>:8001/health`

## Troubleshooting

### Check Service Status
```bash
systemctl status perf-platform
systemctl status nginx
```

### View Logs
```bash
journalctl -u perf-platform -f
tail -f /var/log/nginx/error.log
```

### Restart Services
```bash
systemctl restart perf-platform
systemctl restart nginx
```

### Health Check
```bash
/opt/perf-platform/health_check.py
```

## File Locations

After deployment, files are located at:

```
/opt/perf-platform/
├── run.py                    # Main application
├── backend/                  # Backend modules
├── static/                   # Frontend files
├── scripts/                  # Automation scripts
├── configs/                  # Server configurations
├── data/                     # Runtime data
├── logs/                     # Application logs
├── cli.py                    # CLI tool
└── health_check.py           # Health check
```

## Next Steps

1. **Configure your target server** in the config files
2. **Run the quick test** to verify everything works
3. **Start testing** with your actual target servers
4. **Monitor performance** using the web dashboard
5. **Generate reports** for analysis

The platform is now fully deployed and ready for comprehensive testing!

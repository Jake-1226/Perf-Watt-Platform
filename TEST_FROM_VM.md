# Testing from the VM - Complete Guide

This guide shows how to test the Performance Test Platform directly from the deployed VM.

## 🚀 Quick Start Testing

### 1. Access the VM

```bash
# SSH to the VM (replace with your actual IP and user)
ssh root@<VM_IP>

# Or if using SSH key:
ssh -i /path/to/key root@<VM_IP>
```

### 2. Run Quick Test

```bash
# Run the quick test script
/opt/perf-platform/scripts/quick_test.sh
```

### 3. Access Web Interface

Open your browser and navigate to:
- **Web UI**: `http://<VM_IP>`
- **API**: `http://<VM_IP>:8001/api/`

## 📋 Complete Testing Workflow

### Step 1: Verify Platform Status

```bash
# Check service status
systemctl status perf-platform

# Check if port is listening
netstat -ln | grep 8001

# Check health
/opt/perf-platform/health_check.py

# View logs
journalctl -u perf-platform -f
```

### Step 2: Test API Endpoints

```bash
# Test basic API
curl http://localhost:8001/api/configs

# Test connection status
curl http://localhost:8001/api/connection_status

# Test health endpoint
curl http://localhost:8001/health
```

### Step 3: Test CLI Tool

```bash
# Test CLI health check
/opt/perf-platform/cli.py health

# Test CLI status
/opt/perf-platform/cli.py status

# List available commands
/opt/perf-platform/cli.py --help
```

### Step 4: Configure Target Server

```bash
# Edit test configuration
nano /opt/perf-platform/configs/test_server.json

# Example configuration:
{
  "name": "Test Server",
  "os_ip": "192.168.1.100",
  "os_user": "dell",
  "os_pass": "calvin",
  "idrac_ip": "192.168.1.101",
  "idrac_user": "root",
  "idrac_pass": "calvin",
  "notes": "Test configuration for VM deployment"
}
```

### Step 5: Test Connection to Target Server

```bash
# Connect to target server
/opt/perf-platform/cli.py connect /opt/perf-platform/configs/test_server.json

# Run sanity check
curl -X POST http://localhost:8001/api/sanity_check
```

### Step 6: Run Quick Test (No Target Required)

```bash
# Run quick automated test (simulated)
/opt/perf-platform/scripts/run_automated_test.sh --quick

# Monitor the test
/opt/perf-platform/cli.py run --monitor
```

### Step 7: Run Full Test (With Target Server)

```bash
# Run full test with actual target
/opt/perf-platform/cli.py run --config /opt/perf-platform/configs/test_server.json

# Or use automated script
/opt/perf-platform/scripts/run_automated_test.sh \
  --config /opt/perf-platform/configs/test_server.json \
  --quick
```

## 🔧 Advanced Testing

### Test Different Scenarios

```bash
# Test with custom phase duration
/opt/perf-platform/cli.py run --phase-duration 60 --rest-duration 15

# Test with custom configuration
cat > /opt/perf-platform/configs/custom_test.json << EOF
{
  "name": "Custom Test",
  "os_ip": "192.168.1.100",
  "os_user": "dell",
  "os_pass": "calvin",
  "idrac_ip": "192.168.1.101",
  "idrac_user": "root",
  "idrac_pass": "calvin"
}
EOF

/opt/perf-platform/cli.py run --config /opt/perf-platform/configs/custom_test.json
```

### Test Telemetry Collection

```bash
# Get latest telemetry
curl http://localhost:8001/api/telemetry/latest

# Get OS metrics
curl http://localhost:8001/api/telemetry/os?limit=10

# Get power metrics
curl http://localhost:8001/api/telemetry/power?limit=10
```

### Test Report Generation

```bash
# Generate report
/opt/perf-platform/cli.py report

# Download report
/opt/perf-platform/cli.py report --download

# List runs
/opt/perf-platform/cli.py runs
```

## 📊 Monitoring During Tests

### Real-time Monitoring

```bash
# Monitor system resources
htop

# Monitor network connections
netstat -an | grep 8001

# Monitor disk usage
df -h /opt/perf-platform

# Monitor service logs
journalctl -u perf-platform -f
```

### WebSocket Testing

```bash
# Test WebSocket connection (using wscat)
wscat -c ws://localhost:8001/ws

# Or use curl for basic test
curl -i -N -H "Connection: Upgrade" \
     -H "Upgrade: websocket" \
     -H "Sec-WebSocket-Key: test" \
     -H "Sec-WebSocket-Version: 13" \
     http://localhost:8001/ws
```

## 🐛 Troubleshooting

### Common Issues

#### Service Won't Start

```bash
# Check service status
systemctl status perf-platform

# Check logs
journalctl -u perf-platform -n 50

# Check Python environment
/opt/perf-platform/venv/bin/python --version

# Check dependencies
/opt/perf-platform/venv/bin/pip list
```

#### API Not Responding

```bash
# Check if port is listening
netstat -ln | grep 8001

# Check nginx status
systemctl status nginx

# Test direct connection
curl http://localhost:8001/api/configs

# Check nginx logs
tail -f /var/log/nginx/error.log
```

#### Connection to Target Server Fails

```bash
# Test SSH to target server
ssh dell@<TARGET_IP> "echo 'SSH works'"

# Test iDRAC SSH
ssh root@<IDRAC_IP> "thmtest -g s"

# Check configuration file
cat /opt/perf-platform/configs/test_server.json
```

#### Health Check Fails

```bash
# Run health check manually
/opt/perf-platform/health_check.py

# Check each component
ps aux | grep "python run.py"
ls -la /opt/perf-platform/data/platform.db
netstat -ln | grep 8001
```

### Reset and Redeploy

```bash
# Stop services
systemctl stop perf-platform nginx

# Clean data (optional)
rm -rf /opt/perf-platform/data/*
rm -rf /opt/perf-platform/logs/*

# Restart services
systemctl start perf-platform nginx

# Verify deployment
/opt/perf-platform/scripts/quick_test.sh
```

## 📱 Web Interface Testing

### Access Web UI

1. Open browser: `http://<VM_IP>`
2. Navigate through tabs:
   - **Home**: Check saved configurations
   - **Connect**: Enter target server details
   - **Sanity**: Run system check
   - **Config**: Configure test phases
   - **Dashboard**: Monitor live test
   - **Report**: Generate reports

### Test Web Interface Features

```bash
# Test with browser console
# Open developer tools (F12)
# Check for JavaScript errors
# Monitor WebSocket connections in Network tab
# Verify API calls in Network tab
```

## 📈 Performance Testing

### Load Testing

```bash
# Test API performance
ab -n 100 -c 10 http://localhost:8001/api/configs

# Test WebSocket performance
# Use multiple browser tabs to connect to WebSocket
# Monitor system resources during load test
```

### Stress Testing

```bash
# Run multiple concurrent tests
for i in {1..3}; do
  /opt/perf-platform/cli.py run --quick &
done
wait

# Monitor system during stress test
htop
iostat -x 1
```

## 📋 Test Checklist

### Basic Functionality Tests

- [ ] Platform service starts successfully
- [ ] API endpoints respond correctly
- [ ] Web UI loads without errors
- [ ] CLI tool works properly
- [ ] Health check passes
- [ ] Logs are being generated

### Integration Tests

- [ ] Can connect to target server
- [ ] Sanity check runs successfully
- [ ] Test phases execute correctly
- [ ] Telemetry is collected
- [ ] Reports are generated
- [ ] WebSocket streaming works

### Performance Tests

- [ ] Platform responds within acceptable time
- [ ] Memory usage is reasonable
- [ ] CPU usage is normal during idle
- [ ] Disk space usage is acceptable
- [ ] Network performance is good

### Security Tests

- [ ] Firewall rules are in place
- [ ] Only required ports are open
- [ ] Service runs as non-root user
- [ ] Log files have appropriate permissions
- [ ] Configuration files are secure

## 🎯 Success Criteria

The deployment is successful when:

1. ✅ All services are running (perf-platform, nginx)
2. ✅ Web UI is accessible at `http://<VM_IP>`
3. ✅ API is responding at `http://<VM_IP>:8001/api/`
4. ✅ Health check passes
5. ✅ CLI tool works correctly
6. ✅ Can connect to target server (if configured)
7. ✅ Test execution works (quick test)
8. ✅ Reports are generated correctly
9. ✅ Telemetry collection works
10. ✅ WebSocket streaming functions

## 📞 Getting Help

### Log Locations

```bash
# Service logs
journalctl -u perf-platform -f

# Nginx logs
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log

# Application logs
tail -f /opt/perf-platform/logs/perf-platform.log

# Test logs
ls -la /opt/perf-platform/data/
```

### Support Commands

```bash
# Full system status
systemctl status perf-platform nginx
netstat -tlnp
df -h /opt/perf-platform

# Platform diagnostics
/opt/perf-platform/health_check.py
/opt/perf-platform/cli.py health

# Service management
systemctl restart perf-platform
systemctl restart nginx
```

---

## 🚀 Ready for Testing

Once you've completed the deployment and run the quick test successfully, the platform is ready for:

- **Manual testing** via the web interface
- **Automated testing** via CLI tools
- **Integration testing** with target servers
- **Performance testing** with real workloads
- **Monitoring** of all system components

The platform is now fully deployed and ready for comprehensive testing from the VM!

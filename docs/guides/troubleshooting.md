# Troubleshooting Guide

**Author:** Manu Nicholas Jacob  
**Email:** ManuNicholas.Jacob@dell.com  
**Last Updated:** March 4, 2026

This guide covers common issues, error scenarios, and solutions for the Performance Test Platform.

## Quick Diagnostic Checklist

Before diving into specific issues, run this quick diagnostic:

```bash
# 1. Check platform status
python run.py --help
# Should show usage information

# 2. Check dependencies
pip list | grep -E "fastapi|uvicorn|paramiko|websockets|openpyxl"

# 3. Check data directory
ls -la data/
# Should show platform.db and any run directories

# 4. Test basic connectivity
ping <target-server-ip>
ping <idrac-ip>

# 5. For VM deployments, run health check
/opt/perf-platform/health_check.py

# 6. Check service status (VM deployment)
systemctl status perf-platform
```

## VM Deployment Issues

### Service Won't Start

**Symptoms:**
- `systemctl status perf-platform` shows failed/inactive
- Web interface not accessible
- Health check fails

**Solutions:**

```bash
# Check service status
systemctl status perf-platform

# View service logs
journalctl -u perf-platform -n 50

# Check Python environment
/opt/perf-platform/venv/bin/python --version

# Restart service
systemctl restart perf-platform

# Check dependencies
/opt/perf-platform/venv/bin/pip list
```

### Permission Issues

**Symptoms:**
- Permission denied errors
- Service running as wrong user
- Data directory access issues

**Solutions:**

```bash
# Check ownership
ls -la /opt/perf-platform/

# Fix permissions
chown -R perf-platform:perf-platform /opt/perf-platform/
chmod 755 /opt/perf-platform/

# Check service user
id perf-platform
```

### Network/Port Issues

**Symptoms:**
- Cannot access web interface
- Port 8001 not listening
- Firewall blocking connections

**Solutions:**

```bash
# Check port listening
netstat -ln | grep 8001

# Check firewall status
ufw status

# Open firewall ports
ufw allow 8001/tcp
ufw reload

# Check nginx status
systemctl status nginx
```

## Platform Startup Issues

### Server Won't Start

**Symptoms:**
- `python run.py` shows error and exits
- Port already in use error
- Module import errors

**Solutions:**

```bash
# Check Python version (must be 3.10+)
python --version

# Install missing dependencies
pip install -r requirements.txt

# Check port availability
netstat -an | grep 8001
# If port in use, use different port:
python run.py --port 8002

# Check for syntax errors
python -m py_compile backend/app.py
python -m py_compile static/index.html
```

### Frontend Not Loading

**Symptoms:**
- Browser shows blank page
- "Something went wrong" error
- Console shows JavaScript errors

**Solutions:**

```bash
# Check static files exist
ls -la static/
ls -la static/index.html

# Verify HTML syntax (optional)
npx htmlhint static/index.html

# Check browser console for specific errors
# Open Developer Tools → Console tab

# Common HTM errors to fix:
# - style="string" should be style=${{object}}
# - HTML comments <!-- --> not allowed in HTM templates
# - Missing React dependencies
```

**Common HTM Fixes:**
```javascript
// ❌ Wrong
<div style="color: red;">
<!-- This comment breaks HTM -->

// ✅ Correct  
<div style=${{color: 'red'}}>
{/* Use JS comments in HTM */}
```

## Connection Issues

### SSH Connection Failures

**Symptoms:**
- "OS connection failed" error
- "Authentication failed" message
- Timeout errors

**Diagnostics:**

```bash
# Test SSH manually
ssh <user>@<os-ip> "echo 'SSH works'"

# Check SSH server status
ssh <user>@<os-ip> "systemctl status ssh"

# Verify credentials
ssh <user>@<os-ip> "whoami"
ssh <user>@<os-ip> "sudo whoami"  # Test sudo access
```

**Solutions:**

```bash
# 1. Verify SSH server is running
ssh <user>@<os-ip> "sudo systemctl status sshd"

# 2. Check user permissions
ssh <user>@<os-ip> "groups"  # Should include sudo group

# 3. Test sudo access
ssh <user>@<os-ip> "echo 'test' | sudo -S cat"

# 4. Check for SSH key issues
ssh -v <user>@<os-ip>  # Verbose output shows connection details
```

### iDRAC Connection Issues

**Symptoms:**
- "iDRAC connection failed" error
- "No racadm prompt" message
- "rootshell failed" error

**Diagnostics:**

```bash
# Test iDRAC SSH
ssh root@<idrac-ip>
# Should show: racadm>>

# Test racadm to rootshell navigation
ssh root@<idrac-ip>
racadm>> rootshell
# Should show: # prompt

# Test thmtest command
ssh root@<idrac-ip>
racadm>> rootshell
# thmtest -g s
```

**Solutions:**

```bash
# 1. Enable SSH on iDRAC (if not enabled)
# Via iDRAC web UI:
# Configuration → Services → SSH → Enable

# 2. Reset iDRAC SSH service
ssh root@<idrac-ip>
racadm>> set iDRAC.SSH.Enable 0
racadm>> set iDRAC.SSH.Enable 1

# 3. Check iDRAC firmware version
racadm getversion
# Older firmware may have different command syntax

# 4. Test alternative access
# If SSH fails, try web UI or Redfish API
curl -k -u root:calvin https://<idrac-ip>/redfish/v1/Systems/System.Embedded.1/Power
```

## Benchmark Execution Issues

### Dependencies Missing

**Symptoms:**
- "stress-ng not found" warnings
- "fio: command not found" errors
- HPL build failures

**Diagnostics:**

```bash
# Check tool availability on server
ssh <user>@<os-ip> "which stress-ng fio bc gcc gfortran mpirun"

# Check package manager
ssh <user>@<os-ip> "which apt-get || which yum"

# Check system info
ssh <user>@<os-ip> "cat /etc/os-release"
```

**Solutions:**

```bash
# Let platform install automatically
# The install_deps action handles this

# Manual installation (Ubuntu/Debian)
ssh <user>@<os-ip> "sudo apt-get update && sudo apt-get install -y stress-ng fio bc gcc gfortran libopenmpi-dev openmpi-bin"

# Manual installation (CentOS/RHEL)
ssh <user>@<os-ip> "sudo yum install -y stress-ng fio bc gcc gcc-gfortran openmpi-devel"
```

### HPL Build Failures

**Symptoms:**
- "ERROR: HPL build failed"
- Permission denied errors
- Missing libraries

**Diagnostics:**

```bash
# Check HPL directory
ssh <user>@<os-ip> "ls -la ~/hpl/"

# Check build logs
ssh <user>@<os-ip> "cat ~/hpl/make.log 2>/dev/null || echo 'No build log'"

# Check dependencies
ssh <user>@<os-ip> "which mpicc gcc gfortran"
```

**Solutions:**

```bash
# 1. Clean and rebuild
ssh <user@os-ip> "rm -rf ~/hpl"

# 2. Check MPI installation
ssh <user>@<os-ip> "mpicc --showme:compile"
ssh <user>@<os-ip> "mpicc --showme:link"

# 3. Fix permissions (common issue)
ssh <user>@<os-ip> "sudo chown -R $(whoami):$(whoami) ~/hpl"

# 4. Rebuild with platform
# Platform will automatically rebuild on next HPL phase
```

### FIO Target Issues

**Symptoms:**
- "FIO: No valid targets found"
- "No space left on device" errors
- FIO using /tmp instead of NVMe drives

**Diagnostics:**

```bash
# Check NVMe mounts
ssh <user>@<os-ip> "df -h | grep nvme"

# Check mount points
ssh <user>@<os-ip> "mount | grep nvme"

# Check disk space
ssh <user>@<os-ip> "df -BG /mnt/nvme*"

# Check permissions
ssh <user>@<os-ip> "ls -la /mnt/nvme*"
```

**Solutions:**

```bash
# 1. Mount NVMe drives if needed
ssh <user>@<os-ip> "sudo mount /dev/nvme2n1 /mnt/nvme2n1"

# 2. Fix permissions
ssh <user>@<os-ip> "sudo chmod 755 /mnt/nvme*"

# 3. Check for small partitions
ssh <user>@<os-ip> "df -BG /mnt/nvme* | awk '$4+0<2 {print $1}'"
# Partitions with <2GB free will be excluded

# 4. Manual FIO test
ssh <user>@<os-ip> "fio --name=test --directory=/mnt/nvme2n1 --size=1G --rw=randrw --bs=4k --direct=1 --numjobs=1 --runtime=10 --time_based"
```

### stress-ng Issues

**Symptoms:**
- "stress-ng not found, falling back to dd-based CPU stress"
- CPU utilization not reaching target

**Diagnostics:**

```bash
# Check stress-ng installation
ssh <user>@<os-ip> "stress-ng --version"

# Test stress-ng manually
ssh <user>@<os-ip> "stress-ng --cpu 4 --timeout 10s --metrics-brief"

# Monitor CPU during test
ssh <user>@<os-ip> "top -bn1 | grep -E '%Cpu|load'"
```

**Solutions:**

```bash
# Install stress-ng
ssh <user>@<os-ip> "sudo apt-get install stress-ng"

# Verify CPU utilization
ssh <user>@<os-ip> "stress-ng --cpu 4 --timeout 30s &
# In another terminal:
ssh <user>@<os-ip> "top -bn1 | grep 'Cpu(s)'"

# Check for CPU frequency scaling
ssh <user>@<os-ip> "cpupower frequency-info"
```

## Telemetry Issues

### No Telemetry Data

**Symptoms:**
- Dashboard shows no metrics
- Charts remain empty
- WebSocket connects but no data

**Diagnostics:**

```bash
# Check collectors are running
# Look for "InboundCollector started" / "OutboundCollector started" in platform logs

# Check database
ls -la data/<run_id>/telemetry.db
sqlite3 data/<run_id>/telemetry.db ".tables"

# Check WebSocket connection
# Open browser dev tools → Network tab → WebSocket
# Should see connection and messages
```

**Solutions:**

```bash
# 1. Restart test (collectors start with test)
# Stop current test and start new one

# 2. Check database permissions
ls -la data/<run_id>/
chmod 755 data/<run_id>/

# 3. Verify SSH commands work manually
ssh <user>@<os-ip> "cat /proc/stat | head -1"
ssh root@<idrac-ip> "thmtest -g s"
```

### iDRAC Power Data Missing

**Symptoms:**
- Power metrics show 0 or null
- WebSocket shows empty power data
- "iDRAC power sample" missing in sanity check

**Diagnostics:**

```bash
# Test iDRAC access
ssh root@<idrac-ip>
racadm>> rootshell
thmtest -g s

# Check sensor output format
# Should show either pipe-delimited or tabular format

# Check specific sensors
ssh root@<idrac-ip>
racadm>> rootshell
thmtest -g s | grep -E "SYS_PWR_INPUT_AC|CPU_PWR_ALL"
```

**Solutions:**

```bash
# 1. Reset iDRAC services
ssh root@<idrac-ip>
racadm>> set iDRAC.SSH.Enable 0
racadm>> set iDRAC.SSH.Enable 1

# 2. Check iDRAC firmware
racadm getversion
# Update firmware if very old version

# 3. Try alternative sensor names
# Different iDRAC versions may use different sensor names
```

### OS Metrics Missing

**Symptoms:**
- CPU, memory metrics show 0 or null
- OS metrics not updating

**Diagnostics:**

```bash
# Test OS commands manually
ssh <user>@<os-ip> "cat /proc/stat"
ssh <user>@<os-ip> "free -m"
ssh <user>@<os-ip> "cat /proc/loadavg"

# Check for container/virtualization
ssh <user>@<os-ip> "cat /proc/1/cgroup | grep docker"
# Some containers have limited /proc access
```

**Solutions:**

```bash
# 1. Check if running in container
ssh <user>@<os-ip> "cat /.dockerenv 2>/dev/null || echo 'Not in container'"

# 2. Verify command availability
ssh <user>@<os-ip> "which cat free awk"

# 3. Check permissions
ssh <user>@<os-ip> "ls -la /proc/stat /proc/meminfo /proc/loadavg"
```

## Report Generation Issues

### Report Generation Fails

**Symptoms:**
- "Report generation failed" error
- Excel file corrupted or incomplete
- Missing sheets or data

**Diagnostics:**

```bash
# Check database exists and has data
ls -la data/<run_id>/telemetry.db
sqlite3 data/<run_id>/telemetry.db "SELECT COUNT(*) FROM os_metrics"
sqlite3 data/<run_id>/telemetry.db "SELECT COUNT(*) FROM power_metrics"

# Check file permissions
ls -la data/<run_id>/
```

**Solutions:**

```bash
# 1. Verify database integrity
sqlite3 data/<run_id>/telemetry.db "PRAGMA integrity_check"

# 2. Check available disk space
df -h data/

# 3. Regenerate report
# Delete existing report and regenerate
rm data/<run_id>/report_<run_id>.xlsx
# Generate again via UI
```

### Excel File Issues

**Symptoms:**
- Excel file won't open
- Charts missing or corrupted
- Data formatting issues

**Diagnostics:**

```bash
# Check file size
ls -lh data/<run_id>/report_<run_id>.xlsx
# Should be >1MB for typical test

# Try opening in different Excel version
# Some older versions may have compatibility issues
```

**Solutions:**

```bash
# 1. Use CSV exports instead
# CSV files are more universally compatible
cp data/<run_id>/os_metrics.csv ./
cp data/<run_id>/power_metrics.csv ./

# 2. Regenerate with different format
# Check if openpyxl version is compatible
pip show openpyxl

# 3. Manual data analysis
# Use Python pandas for analysis:
python -c "
import pandas as pd
import sqlite3
conn = sqlite3.connect('data/<run_id>/telemetry.db')
df = pd.read_sql('SELECT * FROM os_metrics', conn)
print(df.describe())
"
```

## Performance Issues

### Slow Performance

**Symptoms:**
- UI response is slow
- WebSocket updates lagging
- High CPU/memory usage on operator machine

**Diagnostics:**

```bash
# Check platform resource usage
top -p $(pgrep -f "python run.py")

# Check network latency
ping <target-server-ip>
ping <idrac-ip>

# Check database size
du -sh data/
```

**Solutions:**

```bash
# 1. Reduce telemetry frequency
# Modify backend/telemetry.py collection intervals
# InboundCollector: increase from 2s to 5s
# OutboundCollector: increase from 5s to 10s

# 2. Limit WebSocket connections
# Platform supports multiple browsers but each adds overhead

# 3. Clean up old test runs
find data/ -type d -name "20*" -mtime +30 -exec rm -rf {} \;
```

### Memory Leaks

**Symptoms:**
- Memory usage increases over time
- Platform becomes unresponsive after long runs

**Diagnostics:**

```bash
# Monitor memory usage
watch -n 5 'ps aux | grep python | grep run.py'

# Check for memory leaks in Python
pip install memory_profiler
python -m memory_profiler run.py
```

**Solutions:**

```bash
# 1. Restart platform periodically
# For very long-running operations

# 2. Limit data retention
# Implement automatic cleanup of old runs

# 3. Check for unclosed database connections
# Ensure all SQLite connections are properly closed
```

## Error Recovery

### Database Corruption

**Symptoms:**
- SQLite database errors
- "database disk image is malformed"

**Diagnostics:**

```bash
# Check database integrity
sqlite3 data/<run_id>/telemetry.db "PRAGMA integrity_check"

# Check platform database
sqlite3 data/platform.db "PRAGMA integrity_check"
```

**Solutions:**

```bash
# 1. Recover from backup
# If you have recent backups

# 2. Export and recreate
# Export data before corruption:
sqlite3 data/<run_id>/telemetry.db ".dump" > backup.sql
# Create new database and import:
sqlite3 new_telemetry.db < backup.sql

# 3. Reset platform database (last resort)
rm data/platform.db
# Restart platform to recreate
```

### Test Run Stuck

**Symptoms:**
- Test shows "running" but not progressing
- Phase stuck for long time
- No log updates

**Diagnostics:**

```bash
# Check test status
curl http://localhost:8001/api/test/status

# Check for stuck processes on server
ssh <user>@<os-ip> "ps aux | grep -E 'stress-ng|fio|xhpl'"

# Check platform logs for errors
# Look in console output where platform is running
```

**Solutions:**

```bash
# 1. Force stop test
curl -X POST http://localhost:8001/api/test/stop

# 2. Kill processes manually
ssh <user>@<os-ip> "sudo pkill -f stress-ng"
ssh <user>@<os-ip> "sudo pkill -f fio"
ssh <user>@<os-ip> "sudo pkill -f xhpl"

# 3. Restart platform
# Stop and restart the platform service
```

## Getting Help

### Collect Debug Information

When reporting issues, collect this information:

```bash
# 1. Platform version
git log --oneline -1

# 2. Python environment
pip list | grep -E "fastapi|uvicorn|paramiko|websockets|openpyxl"

# 3. System information
python --version
uname -a

# 4. Platform logs
# Save console output when platform starts

# 5. Test run information
# Run ID, error messages, timestamps

# 6. Server information
ssh <user>@<os-ip> "uname -a; cat /etc/os-release; lscpu"
ssh root@<idrac-ip> "racadm getversion"
```

### Log Locations

**Platform Logs:**
- Console output when running `python run.py`
- Browser developer console for frontend errors

**Server Logs:**
- Benchmark logs: `/api/test/logs` endpoint
- SSH session logs in platform console

**Database Logs:**
- SQLite errors appear in platform console
- Check database integrity with `PRAGMA integrity_check`

### Common Error Messages

| Error Message | Likely Cause | Solution |
|---------------|--------------|----------|
| "OS not connected" | SSH connection failed | Check SSH credentials and connectivity |
| "iDRAC connection failed" | iDRAC SSH issues | Check iDRAC SSH enable and credentials |
| "No valid targets found" | FIO can't find drives | Check NVMe mounts and permissions |
| "stress-ng not found" | Missing dependencies | Install stress-ng on server |
| "Database disk image is malformed" | SQLite corruption | Recover from backup or recreate database |
| "WebSocket connection failed" | Network issues | Check firewall and port availability |

---

*For additional help, see the [Developer Guide](development.md) or create an issue in the project repository.*

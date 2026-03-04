# Developer Guide

**Author:** Manu Nicholas Jacob  
**Email:** ManuNicholas.Jacob@dell.com  
**Last Updated:** March 4, 2026

This guide covers contributing to the Performance Test Platform, including development setup, code organization, testing, and contribution guidelines.

## Development Environment Setup

### Prerequisites

- Python 3.10 or higher
- Git
- Code editor (VS Code recommended)
- Modern web browser

### Local Development Setup

```bash
# 1. Clone repository
git clone <repository-url>
cd perf-platform

# 2. Create virtual environment
python -m venv venv

# 3. Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Install development dependencies (optional)
pip install pytest pytest-asyncio black flake8 mypy

# 6. Verify setup
python run.py --help
```

### VS Code Configuration

Create `.vscode/settings.json`:

```json
{
  "python.defaultInterpreterPath": "./venv/bin/python",
  "python.linting.enabled": true,
  "python.linting.flake8Enabled": true,
  "python.formatting.provider": "black",
  "python.formatting.blackArgs": ["--line-length", "100"],
  "python.linting.mypyEnabled": true,
  "files.exclude": {
    "**/__pycache__": true,
    "**/*.pyc": true,
    "venv": true,
    "data/**": true
  }
}
```

Create `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Debug Platform",
      "type": "python",
      "request": "launch",
      "program": "run.py",
      "args": ["--port", "8001"],
      "console": "integratedTerminal",
      "cwd": "${workspaceFolder}",
      "env": {
        "PYTHONPATH": "${workspaceFolder}"
      }
    }
  ]
}
```

## Code Organization

### Directory Structure

```
perf-platform/
├── backend/                  # Backend Python modules
│   ├── __init__.py
│   ├── app.py               # FastAPI application (main entry)
│   ├── ssh_manager.py       # SSH connections (OS + iDRAC)
│   ├── benchmarks.py        # Benchmark orchestrator + agent script
│   ├── telemetry.py         # Telemetry collectors
│   ├── config_db.py         # Persistent configuration DB
│   └── reports.py           # Excel report generation
├── static/
│   └── index.html           # React frontend (single file)
├── test_*.py               # Test scripts
├── run.py                  # Application entry point
└── requirements.txt         # Python dependencies
```

### Module Responsibilities

#### `backend/app.py` (577 lines)
- **FastAPI application**: REST API endpoints, WebSocket server
- **Static file serving**: Serves frontend HTML/CSS/JS
- **Request handling**: Connection management, test control, telemetry access
- **Async coordination**: Thread pool for blocking SSH calls
- **WebSocket broadcasting**: Real-time telemetry and log streaming

#### `backend/ssh_manager.py` (323 lines)
- **OS SSH connection**: Standard paramiko client for command execution
- **iDRAC SSH connection**: Interactive shell navigation (racadm → rootshell)
- **File operations**: SFTP upload/download for benchmark agent
- **System info collection**: Comprehensive server information gathering
- **Power sensor parsing**: Handle multiple iDRAC output formats

#### `backend/benchmarks.py` (619 lines)
- **Benchmark orchestrator**: Phase execution, parallel jobs, cleanup
- **Agent script**: 350-line Bash script for remote benchmark execution
- **HPL management**: Download, build, configure, execute HPL
- **FIO configuration**: Dynamic target discovery and job generation
- **Process management**: Background execution with proper cleanup

#### `backend/telemetry.py` (406 lines)
- **InboundCollector**: OS metrics collection (CPU, memory, load, processes)
- **OutboundCollector**: iDRAC power/thermal collection via thmtest
- **Database operations**: SQLite time-series storage and retrieval
- **Metric calculation**: CPU percentage from /proc/stat deltas
- **Thread management**: Daemon threads with graceful shutdown

#### `backend/config_db.py` (275 lines)
- **Platform database**: SQLite DB for configs, sanity results, run history
- **Schema management**: Table creation, migrations, data integrity
- **CRUD operations**: Server configs, test runs, sanity results
- **JSON handling**: Serialize/deserialize complex data structures
- **Thread safety**: Locking for concurrent database access

#### `backend/reports.py` (443 lines)
- **Excel generation**: 7-sheet workbook with charts and formatting
- **Data aggregation**: Per-phase statistics and summaries
- **Chart creation**: Embedded charts for trends and analysis
- **Export functionality**: CSV exports for external analysis
- **Styling**: Professional formatting with headers and borders

#### `static/index.html` (654 lines)
- **React frontend**: Single-page application with HTM templates
- **UI components**: 6 panels (Home, Connect, Sanity, Config, Dashboard, Report)
- **Real-time updates**: WebSocket integration for live telemetry
- **Charts**: Recharts integration for time-series visualization
- **Error handling**: Error boundaries and toast notifications

## Development Workflow

### 1. Making Changes

#### Backend Changes

```bash
# 1. Make code changes
# 2. Run linting
flake8 backend/
black backend/

# 3. Run type checking
mypy backend/

# 4. Test manually
python run.py --port 8001
# Open browser to http://localhost:8001
# Test affected functionality

# 5. Run automated tests
python test_e2e.py
```

#### Frontend Changes

```bash
# 1. Edit static/index.html
# 2. Validate HTML (optional)
npx htmlhint static/index.html

# 3. Test in browser
python run.py --port 8001
# Open browser developer tools
# Check console for errors
# Test UI functionality

# 4. Test WebSocket functionality
# Open browser network tab
# Verify WebSocket messages
```

### 2. Testing

#### Running Tests

```bash
# End-to-end test (comprehensive)
python test_e2e.py

# WebSocket test
python test_live_ws.py

# API test
python test_run.py

# Manual test with specific server
python test_full.py
```

#### Test Structure

- **test_e2e.py**: Full end-to-end test with real server connection
- **test_live_ws.py**: WebSocket functionality test
- **test_run.py**: API endpoint testing
- **test_full.py**: Manual verification test

#### Writing New Tests

```python
# Example test structure
import pytest
import asyncio
from backend.app import app
from backend.ssh_manager import SSHManager

@pytest.mark.asyncio
async def test_api_endpoint():
    """Test a specific API endpoint"""
    from fastapi.testclient import TestClient
    client = TestClient(app)
    
    response = client.get("/api/configs")
    assert response.status_code == 200
    assert "configs" in response.json()

def test_ssh_connection():
    """Test SSH connection functionality"""
    ssh = SSHManager()
    result = ssh.connect_os("test-server", "user", "pass")
    assert result["status"] in ["connected", "error"]
```

### 3. Debugging

#### Backend Debugging

```python
# Add debug prints
import logging
logging.basicConfig(level=logging.DEBUG)

# Use VS Code debugger
# Set breakpoints in code
# Run "Debug Platform" configuration

# Remote debugging (if needed)
import pdb
pdb.set_trace()  # Add where you want to break
```

#### Frontend Debugging

```javascript
// Add console logging
console.log('Debug info:', data);

// Use browser debugger
// Add debugger; statements
// Use browser dev tools breakpoints

// WebSocket debugging
ws.onmessage = (event) => {
    console.log('WS received:', event.data);
};
```

#### Telemetry Debugging

```bash
# Check database contents
sqlite3 data/20260302_162939/telemetry.db
.tables
SELECT * FROM os_metrics LIMIT 5;

# Check SSH commands manually
ssh user@server "cat /proc/stat"
ssh user@server "free -m"

# Check iDRAC access
ssh root@idrac-ip
racadm>> rootshell
thmtest -g s
```

## Coding Standards

### Python Code Style

Follow PEP 8 with these specific guidelines:

```python
# Imports at top
import asyncio
import json
from typing import Optional, Dict, List

# Type hints required for public APIs
def connect_os(ip: str, user: str, password: str) -> Dict[str, str]:
    """Connect to the server OS via SSH.
    
    Args:
        ip: Server IP address
        user: SSH username
        password: SSH password
        
    Returns:
        Dictionary with connection status and details
    """
    return {"status": "connected", "ip": ip}

# Constants at module level
DEFAULT_TIMEOUT = 30
MAX_RETRIES = 3

# Class names PascalCase
class SSHManager:
    """Manages SSH connections to OS and iDRAC."""
    
    def __init__(self) -> None:
        self.os_client: Optional[paramiko.SSHClient] = None
        
    def _log(self, message: str) -> None:
        """Log a message with timestamp."""
        print(f"[{datetime.now()}] {message}")

# Function names snake_case
def get_system_info() -> Dict[str, str]:
    """Collect comprehensive system information."""
    return {}

# Variable names snake_case
current_phase = "idle_baseline"
connection_status = "connected"

# Private methods start with underscore
def _validate_config(self, config: Dict) -> bool:
    """Validate configuration dictionary."""
    return True
```

### Frontend Code Style

```javascript
// Use modern JavaScript features
const connectToServer = async (config) => {
    try {
        const response = await fetch('/api/connect', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(config)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('Connection failed:', error);
        throw error;
    }
};

// Use descriptive variable names
const serverConfiguration = {
    os_ip: '192.168.1.100',
    os_user: 'dell',
    idrac_ip: '192.168.1.101'
};

// Component functions with clear names
function ConnectionPanel({onConnect, connectionStatus}) {
    const [config, setConfig] = useState({});
    
    const handleSubmit = useCallback(async () => {
        try {
            await onConnect(config);
            showSuccessToast('Connected successfully');
        } catch (error) {
            showErrorToast(error.message);
        }
    }, [config, onConnect]);
    
    return html`
        <div class="connection-panel">
            <!-- Panel content -->
        </div>
    `;
}
```

### Documentation Standards

```python
def complex_function(param1: str, param2: int, param3: Optional[Dict] = None) -> Dict[str, Any]:
    """This is a one-line summary of the function.
    
    A more detailed description that spans multiple lines and explains
    the function's behavior, parameters, and return value.
    
    Args:
        param1: Description of the first parameter
        param2: Description of the second parameter
        param3: Optional parameter with default behavior
        
    Returns:
        Dictionary containing:
            - 'status': Operation status ('success' or 'error')
            - 'data': Result data if successful
            - 'error': Error message if failed
            
    Raises:
        ValueError: When param1 is invalid
        ConnectionError: When server cannot be reached
        
    Example:
        >>> result = complex_function("test", 42)
        >>> print(result['status'])
        'success'
    """
    pass
```

## Adding New Features

### 1. New Benchmark Type

To add a new benchmark (e.g., memory stress test):

#### Backend Changes

```python
# 1. Add to benchmarks.py BENCHMARK_AGENT_SCRIPT
run_memory_stress)
    SIZE="$1"; DURATION="$2"
    log "Memory stress: size=${SIZE}, duration=${DURATION}s"
    # Implementation here
    ;;

# 2. Add to BenchmarkOrchestrator._run_sequence
elif phase_type == "memory_stress":
    size = phase_cfg.get("size", "1G")
    self._run_benchmark(
        self._sudo_cmd(f"run_memory_stress {size} {duration}"),
        duration, phase_name)

# 3. Add to _default_phases in app.py
{"name": "09_memory_stress", "type": "memory_stress", "duration": duration}
```

#### Frontend Changes

```javascript
// Add to phase type options in ConfigPanel
const PHASE_TYPES = [
    {value: 'idle', label: 'Idle'},
    {value: 'hpl_100', label: 'HPL 100%'},
    {value: 'memory_stress', label: 'Memory Stress'},
    // ...
];
```

### 2. New Telemetry Metric

To add a new OS metric (e.g., network interface stats):

```python
# 1. Add to InboundCollector.run()
# Network interface stats
out, _, _ = self.ssh.os_exec(
    "cat /proc/net/dev | grep eth0", timeout=5)
if out.strip():
    parts = out.strip().split()
    metrics["net_rx_bytes"] = int(parts[1])
    metrics["net_tx_bytes"] = int(parts[9])

# 2. Add to telemetry.py database schema
# (Requires migration logic)
c.execute("""ALTER TABLE os_metrics ADD COLUMN net_rx_bytes INTEGER""")
c.execute("""ALTER TABLE os_metrics ADD COLUMN net_tx_bytes INTEGER""")
```

### 3. New API Endpoint

```python
# 1. Add to app.py
@app.get("/api/custom/metrics")
async def get_custom_metrics():
    """Get custom metrics for advanced analysis."""
    if not telemetry.DB_PATH:
        raise HTTPException(400, "No test data available")
    
    # Custom query logic
    conn = sqlite3.connect(telemetry.DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT phase, AVG(cpu_pct) as avg_cpu, COUNT(*) as samples
        FROM os_metrics 
        WHERE phase != '' 
        GROUP BY phase
    """)
    
    results = [{"phase": row[0], "avg_cpu": row[1], "samples": row[2]} 
              for row in c.fetchall()]
    conn.close()
    
    return {"data": results}
```

## Performance Optimization

### Backend Optimization

```python
# Use connection pooling for database
from contextlib import contextmanager

@contextmanager
def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

# Cache frequently accessed data
from functools import lru_cache

@lru_cache(maxsize=128)
def get_config(config_id: int):
    return config_db.get_config(config_id)

# Use async operations where possible
async def collect_metrics_async():
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, collect_metrics)
```

### Frontend Optimization

```javascript
// Debounce WebSocket updates
const useDebounce = (func, delay) => {
    const timeoutRef = useRef(null);
    
    return useCallback((...args) => {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = setTimeout(() => func(...args), delay);
    }, [func, delay]);
};

// Memoize expensive calculations
const memoizedData = useMemo(() => {
    return processLargeDataset(rawData);
}, [rawData]);

// Virtual scrolling for large lists
import { FixedSizeList as List } from 'react-window';

function LogViewer({logs}) {
    const Row = ({index, style}) => (
        <div style={style}>{logs[index]}</div>
    );
    
    return (
        <List
            height={400}
            itemCount={logs.length}
            itemSize={20}
        >
            {Row}
        </List>
    );
}
```

## Troubleshooting Development Issues

### Common Development Problems

#### Import Errors

```bash
# Check Python path
python -c "import sys; print(sys.path)"

# Install in development mode
pip install -e .

# Check virtual environment
which python
python --version
```

#### Frontend Not Updating

```bash
# Clear browser cache
# Open developer tools
# Right-click refresh → "Empty Cache and Hard Reload"

# Check for syntax errors
# Browser console will show HTM parsing errors
```

#### Database Issues

```bash
# Check database integrity
sqlite3 data/platform.db "PRAGMA integrity_check;"

# Reset database (development only)
rm data/platform.db
# Restart server to recreate
```

#### SSH Connection Issues

```bash
# Test SSH manually
ssh user@server "echo 'SSH works'"

# Check paramiko version
pip show paramiko

# Enable debug logging
import paramiko
paramiko.util.log_to_file('ssh_debug.log')
```

### Performance Debugging

```python
# Profile slow functions
import cProfile
import pstats

def profile_function(func):
    profiler = cProfile.Profile()
    profiler.enable()
    result = func()
    profiler.disable()
    
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats(10)
    
    return result

# Memory usage tracking
import tracemalloc

tracemalloc.start()
# ... run code ...
current, peak = tracemalloc.get_traced_memory()
print(f"Current memory usage: {current / 1024 / 1024:.1f} MB")
print(f"Peak memory usage: {peak / 1024 / 1024:.1f} MB")
```

## Contributing Guidelines

### Pull Request Process

1. **Fork repository** and create feature branch
2. **Make changes** following coding standards
3. **Add tests** for new functionality
4. **Update documentation** as needed
5. **Run full test suite** and ensure all pass
6. **Submit pull request** with clear description

### Pull Request Requirements

- **Tests pass**: All automated tests must pass
- **Code style**: Follows project coding standards
- **Documentation**: Updated for any API/UI changes
- **No breaking changes**: Unless clearly documented and necessary
- **Performance**: No significant performance regressions

### Code Review Checklist

- [ ] Code follows project style guidelines
- [ ] Tests cover new functionality
- [ ] Documentation is updated
- [ ] Error handling is appropriate
- [ ] No hardcoded credentials or paths
- [ ] WebSocket messages are properly formatted
- [ ] Database operations are thread-safe
- [ ] Frontend handles errors gracefully

### Release Process

1. **Update version** in appropriate files
2. **Update CHANGELOG** with new features and fixes
3. **Tag release** in Git
4. **Create release** on GitHub
5. **Update documentation** if needed

---

*For deployment and setup instructions, see the [Deployment Guide](deployment.md).*

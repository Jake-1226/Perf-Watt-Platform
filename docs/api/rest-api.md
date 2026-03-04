# REST API Reference

**Author:** Manu Nicholas Jacob  
**Email:** ManuNicholas.Jacob@dell.com  
**Last Updated:** March 4, 2026

The Performance Test Platform provides a comprehensive REST API for configuration, test control, telemetry access, and report generation. All endpoints return JSON responses unless otherwise specified.

**Base URL**: `http://localhost:8001` (or configured port)

## Authentication

The API does not require authentication keys. All connections are handled through the UI's WebSocket session and standard HTTP requests.

## CLI Tool Integration

The platform includes a CLI tool (`/opt/perf-platform/cli.py`) that provides convenient access to the API:

```bash
# Health check
/opt/perf-platform/cli.py health

# Test status
/opt/perf-platform/cli.py status

# Run automated test
/opt/perf-platform/scripts/run_automated_test.sh --quick
```

The CLI tool internally calls the same REST API endpoints documented below.

## Response Format

### Success Responses
```json
{
  "field": "value",
  "data": [...],
  "status": "success"
}
```

### Error Responses
```json
{
  "detail": "Error description",
  "status": "error"
}
```

HTTP status codes follow REST conventions:
- `200` - Success
- `400` - Bad Request
- `404` - Not Found
- `500` - Internal Server Error

---

## Configuration Endpoints

### List Server Configurations

**GET** `/api/configs`

Retrieve all saved server connection profiles.

**Response:**
```json
{
  "configs": [
    {
      "id": 1,
      "name": "Production Server",
      "created_at": "2026-03-02T16:00:00Z",
      "updated_at": "2026-03-02T16:00:00Z",
      "os_ip": "192.168.1.100",
      "os_user": "dell",
      "idrac_ip": "192.168.1.101",
      "idrac_user": "root",
      "notes": "Main production server"
    }
  ]
}
```

### Save Server Configuration

**POST** `/api/configs`

Create or update a server configuration.

**Request Body:**
```json
{
  "name": "Test Server",
  "os_ip": "192.168.1.100",
  "os_user": "dell",
  "os_pass": "calvin",
  "idrac_ip": "192.168.1.101",
  "idrac_user": "root",
  "idrac_pass": "calvin",
  "notes": "Test environment"
}
```

**Response:**
```json
{
  "config_id": 2,
  "status": "saved"
}
```

### Get Server Configuration

**GET** `/api/configs/{id}`

Retrieve a specific server configuration by ID (includes passwords).

**Path Parameters:**
- `id` (integer) - Configuration ID

**Response:**
```json
{
  "id": 1,
  "name": "Production Server",
  "created_at": "2026-03-02T16:00:00Z",
  "updated_at": "2026-03-02T16:00:00Z",
  "os_ip": "192.168.1.100",
  "os_user": "dell",
  "os_pass": "calvin",
  "idrac_ip": "192.168.1.101",
  "idrac_user": "root",
  "idrac_pass": "calvin",
  "notes": "Main production server"
}
```

### Delete Server Configuration

**DELETE** `/api/configs/{id}`

Delete a server configuration and its associated sanity results.

**Path Parameters:**
- `id` (integer) - Configuration ID

**Response:**
```json
{
  "status": "deleted"
}
```

### Get Sanity Result for Configuration

**GET** `/api/configs/{id}/sanity`

Retrieve the latest sanity check result for a configuration.

**Path Parameters:**
- `id` (integer) - Configuration ID

**Response:**
```json
{
  "sanity": {
    "id": 1,
    "config_id": 1,
    "checked_at": "2026-03-02T16:00:00Z",
    "os": {
      "sysinfo": {
        "hostname": "test-server",
        "cpu_cores": "96",
        "memory_total_gb": "512"
      }
    },
    "idrac": {
      "sysinfo": {
        "idrac_version": "7.0.0",
        "service_tag": "ABC123"
      },
      "thmtest_sample": {
        "SYS_PWR_INPUT_AC": 450.5,
        "CPU_PWR_ALL": 120.3,
        "DIMM_PWR_ALL": 45.2
      },
      "thmtest_ok": true
    },
    "capabilities": {
      "gcc": true,
      "fio": true,
      "stress-ng": true,
      "mpicc": true
    }
  }
}
```

---

## Connection Endpoints

### Connect to Server

**POST** `/api/connect`

Establish SSH connections to the server OS and optionally iDRAC.

**Request Body:**
```json
{
  "os_ip": "192.168.1.100",
  "os_user": "dell",
  "os_pass": "calvin",
  "idrac_ip": "192.168.1.101",
  "idrac_user": "root",
  "idrac_pass": "calvin",
  "config_id": 1,
  "save_as": "Production Server"
}
```

**Optional Fields:**
- `config_id` - Use existing configuration
- `save_as` - Save new configuration with this name

**Response:**
```json
{
  "os": {
    "status": "connected",
    "ip": "192.168.1.100",
    "user": "dell"
  },
  "idrac": {
    "status": "connected",
    "ip": "192.168.1.101"
  },
  "config_id": 1
}
```

### Disconnect from Server

**POST** `/api/disconnect`

Close all SSH connections and stop telemetry collectors.

**Response:**
```json
{
  "status": "disconnected"
}
```

### Get Connection Status

**GET** `/api/connection_status`

Check current connection status.

**Response:**
```json
{
  "os_connected": true,
  "idrac_connected": true
}
```

---

## Sanity Check

### Run Sanity Check

**POST** `/api/sanity_check`

Perform comprehensive system check and cache results.

**Query Parameters:**
- `config_id` (optional, integer) - Configuration ID to associate results with

**Response:**
```json
{
  "os": {
    "sysinfo": {
      "hostname": "test-server",
      "os_release": "Ubuntu 24.04 LTS",
      "kernel": "6.5.0-28-generic",
      "cpu_model": "Intel Xeon Platinum 8360Y",
      "cpu_cores": "96",
      "memory_total_gb": "512",
      "disk_info": "nvme0n1 3.5T disk, nvme1n1 3.5T disk",
      "nvme_drives": "nvme2n1 3.5T disk, nvme3n1 3.5T disk"
    }
  },
  "idrac": {
    "sysinfo": {
      "idrac_version": "7.0.0.0",
      "service_tag": "ABC123",
      "bios_version": "2.5.3"
    },
    "thmtest_sample": {
      "SYS_PWR_INPUT_AC": 450.5,
      "CPU_PWR_ALL": 120.3,
      "DIMM_PWR_ALL": 45.2,
      "STORAGE_PWR": 15.8,
      "FAN_PWR_MAIN": 8.5,
      "INLET_TEMP": 22.5,
      "EXHAUST_TEMP": 35.2,
      "CPU_TEMP": 65.0
    },
    "thmtest_ok": true
  },
  "capabilities": {
    "gcc": true,
    "gfortran": true,
    "mpicc": true,
    "mpirun": true,
    "fio": true,
    "stress-ng": true,
    "bc": true,
    "wget": true
  }
}
```

---

## Test Execution

### Start Test

**POST** `/api/test/start`

Initiate a benchmark test run.

**Request Body:**
```json
{
  "phase_duration": 30,
  "rest_duration": 10,
  "phases": [
    {
      "name": "01_idle_baseline",
      "type": "idle",
      "duration": 10
    },
    {
      "name": "02_hpl_100pct",
      "type": "hpl_100",
      "duration": 30
    }
  ],
  "config_id": 1
}
```

**Response:**
```json
{
  "status": "started",
  "run_id": "20260302_162939",
  "config": {
    "phase_duration": 30,
    "rest_duration": 10,
    "total_cores": 96,
    "fio_targets": "/mnt/nvme2n1 /mnt/nvme3n1 /mnt/nvme5n1",
    "phases": [...]
  }
}
```

### Stop Test

**POST** `/api/test/stop`

Terminate the currently running test and clean up processes.

**Response:**
```json
{
  "status": "stopped"
}
```

### Get Test Status

**GET** `/api/test/status`

Retrieve current test execution status.

**Response:**
```json
{
  "running": true,
  "current_phase": "02_hpl_100pct",
  "run_id": "20260302_162939",
  "log_lines": 1250,
  "os_connected": true,
  "idrac_connected": true
}
```

### Get Test Logs

**GET** `/api/test/logs`

Retrieve benchmark log lines with pagination.

**Query Parameters:**
- `offset` (default: 0) - Starting line number
- `limit` (default: 200) - Maximum lines to return

**Response:**
```json
{
  "lines": [
    "2026-03-02 16:30:00 [AGENT] Installing dependencies...",
    "2026-03-02 16:30:05 [AGENT] stress-ng: OK",
    "2026-03-02 16:30:10 [AGENT] fio: OK"
  ],
  "total": 1250,
  "offset": 0
}
```

---

## Telemetry Endpoints

### Get OS Metrics

**GET** `/api/telemetry/os`

Retrieve OS metrics time-series data.

**Query Parameters:**
- `limit` (default: 300) - Maximum number of samples

**Response:**
```json
{
  "data": [
    {
      "id": 1,
      "timestamp": "2026-03-02T16:30:00Z",
      "epoch": 1709386200.0,
      "phase": "02_hpl_100pct",
      "cpu_pct": 100.0,
      "mem_pct": 15.2,
      "mem_used_mb": 78643,
      "mem_total_mb": 524288,
      "load_1m": 96.0,
      "load_5m": 94.5,
      "load_15m": 88.2,
      "disk_read_kbs": 1024.5,
      "disk_write_kbs": 2048.0,
      "net_rx_kbs": 512.3,
      "net_tx_kbs": 256.7,
      "process_count": 285,
      "top_processes": [
        {"pid": "1234", "comm": "stress-ng", "cpu": "25.5", "mem": "0.1"}
      ]
    }
  ]
}
```

### Get Power Metrics

**GET** `/api/telemetry/power`

Retrieve power/thermal metrics time-series data.

**Query Parameters:**
- `limit` (default: 300) - Maximum number of samples

**Response:**
```json
{
  "data": [
    {
      "id": 1,
      "timestamp": "2026-03-02T16:30:00Z",
      "epoch": 1709386200.0,
      "phase": "02_hpl_100pct",
      "sys_input_ac_w": 450.5,
      "cpu_power_w": 120.3,
      "dimm_power_w": 45.2,
      "storage_power_w": 15.8,
      "fan_power_w": 8.5,
      "inlet_temp_c": 22.5,
      "exhaust_temp_c": 35.2,
      "cpu_temp_c": 65.0,
      "raw_sensors": "{...}"
    }
  ]
}
```

### Get Latest Telemetry

**GET** `/api/telemetry/latest`

Retrieve the most recent telemetry readings.

**Response:**
```json
{
  "os": {
    "cpu_pct": 100.0,
    "mem_pct": 15.2,
    "mem_used_mb": 78643,
    "mem_total_mb": 524288,
    "load_1m": 96.0,
    "load_5m": 94.5,
    "load_15m": 88.2,
    "process_count": 285,
    "top_processes": [...]
  },
  "power": {
    "sys_input_ac_w": 450.5,
    "cpu_power_w": 120.3,
    "dimm_power_w": 45.2,
    "storage_power_w": 15.8,
    "fan_power_w": 8.5,
    "inlet_temp_c": 22.5,
    "exhaust_temp_c": 35.2,
    "cpu_temp_c": 65.0
  }
}
```

### Get Benchmark Events

**GET** `/api/telemetry/events`

Retrieve benchmark lifecycle events.

**Response:**
```json
{
  "data": [
    {
      "id": 1,
      "timestamp": "2026-03-02T16:30:00Z",
      "epoch": 1709386200.0,
      "phase": "02_hpl_100pct",
      "event_type": "phase_start",
      "benchmark": "stress-ng",
      "message": "Starting phase 02_hpl_100pct",
      "data": {"cores": 96, "duration": 30}
    }
  ]
}
```

### Get System Info

**GET** `/api/telemetry/sysinfo`

Retrieve collected system information.

**Response:**
```json
{
  "data": {
    "os": {
      "hostname": "test-server",
      "cpu_model": "Intel Xeon Platinum 8360Y",
      "cpu_cores": "96",
      "memory_total_gb": "512"
    },
    "idrac": {
      "idrac_version": "7.0.0.0",
      "service_tag": "ABC123",
      "bios_version": "2.5.3"
    }
  }
}
```

---

## Report Endpoints

### Generate Report

**POST** `/api/report/generate`

Generate comprehensive Excel report with charts.

**Response:**
```json
{
  "status": "generated",
  "excel_path": "/path/to/data/20260302_162939/report_20260302_162939.xlsx",
  "run_id": "20260302_162939",
  "summary": {
    "phases": [
      {
        "name": "02_hpl_100pct",
        "avg_cpu_pct": 100.0,
        "max_cpu_pct": 100.0,
        "avg_ac_w": 450.5,
        "avg_cpu_w": 120.3
      }
    ],
    "overall": {
      "duration_s": 420,
      "os_samples": 210,
      "power_samples": 84,
      "avg_ac_w": 350.2,
      "min_ac_w": 180.5,
      "max_ac_w": 450.5
    }
  }
}
```

### Download Report

**GET** `/api/report/download/{run_id}`

Download the generated Excel report.

**Path Parameters:**
- `run_id` (string) - Test run identifier

**Response**: Excel file download (`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`)

### Get Report Summary

**GET** `/api/report/summary`

Get JSON summary of the current test run.

**Response:**
```json
{
  "phases": [
    {
      "name": "02_hpl_100pct",
      "os_samples": 60,
      "avg_cpu_pct": 100.0,
      "max_cpu_pct": 100.0,
      "avg_mem_pct": 15.2,
      "pwr_samples": 24,
      "avg_ac_w": 450.5,
      "avg_cpu_w": 120.3,
      "avg_dimm_w": 45.2,
      "avg_stor_w": 15.8,
      "avg_fan_w": 8.5
    }
  ],
  "overall": {
    "duration_s": 420,
    "os_samples": 210,
    "power_samples": 84,
    "avg_ac_w": 350.2,
    "min_ac_w": 180.5,
    "max_ac_w": 450.5
  }
}
```

---

## Run History

### List Test Runs

**GET** `/api/runs`

Retrieve all test runs with metadata.

**Response:**
```json
{
  "runs": [
    {
      "id": 1,
      "run_id": "20260302_162939",
      "config_id": 1,
      "config_name": "Production Server",
      "started_at": "2026-03-02T16:29:39Z",
      "finished_at": "2026-03-02T16:37:39Z",
      "status": "completed",
      "phase_duration": 30,
      "rest_duration": 10,
      "phases": [...],
      "total_cores": 96,
      "fio_targets": "/mnt/nvme2n1 /mnt/nvme3n1",
      "current_phase": "complete",
      "summary": {...},
      "has_report": true,
      "has_os_csv": true,
      "has_power_csv": true,
      "has_data": true
    }
  ]
}
```

### Get Test Run Details

**GET** `/api/runs/{run_id}`

Retrieve detailed information for a specific test run.

**Path Parameters:**
- `run_id` (string) - Test run identifier

**Response**: Same as individual run object in the list response, with full details.

---

## WebSocket API

### Connection

**WebSocket** `/ws`

Real-time bidirectional communication for telemetry and log streaming.

**Connection:**
```javascript
const ws = new WebSocket('ws://localhost:8001/ws');
```

### Message Types

#### Telemetry Update

**Type**: `telemetry`

**Payload:**
```json
{
  "type": "telemetry",
  "os": {
    "cpu_pct": 100.0,
    "mem_pct": 15.2,
    "load_1m": 96.0,
    "process_count": 285
  },
  "power": {
    "sys_input_ac_w": 450.5,
    "cpu_power_w": 120.3,
    "inlet_temp_c": 22.5,
    "cpu_temp_c": 65.0
  },
  "phase": "02_hpl_100pct",
  "running": true
}
```

#### Log Line

**Type**: `log`

**Payload:**
```json
{
  "type": "log",
  "line": "2026-03-02 16:30:00 [AGENT] stress-ng: OK"
}
```

#### Test Complete

**Type**: `test_complete`

**Payload:**
```json
{
  "type": "test_complete",
  "run_id": "20260302_162939"
}
```

### Client Requirements

- Send any message periodically to keep connection alive (ping/pong)
- Handle disconnections gracefully with auto-reconnect
- Process messages asynchronously to avoid blocking

---

## Error Handling

### Common Error Responses

#### 400 Bad Request
```json
{
  "detail": "OS not connected"
}
```

#### 404 Not Found
```json
{
  "detail": "Config not found"
}
```

#### 500 Internal Server Error
```json
{
  "detail": "SSH connection failed: Authentication failed"
}
```

### Error Recovery

- **Connection Errors**: Reconnect via `/api/connect`
- **Test Failures**: Check logs via `/api/test/logs`
- **Missing Data**: Verify iDRAC connectivity and tool availability

---

## Rate Limits

The API does not implement explicit rate limiting, but consider:

- **Telemetry endpoints**: Cache responses for 1-2 seconds
- **Log streaming**: Use pagination to avoid large transfers
- **Concurrent tests**: Only one test can run at a time per backend instance

---

## Example Usage

### Complete Test Flow

```bash
# 1. Save configuration
curl -X POST http://localhost:8001/api/configs \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Server",
    "os_ip": "192.168.1.100",
    "os_user": "dell",
    "os_pass": "calvin",
    "idrac_ip": "192.168.1.101",
    "idrac_user": "root",
    "idrac_pass": "calvin"
  }'

# 2. Connect
curl -X POST http://localhost:8001/api/connect \
  -H "Content-Type: application/json" \
  -d '{
    "os_ip": "192.168.1.100",
    "os_user": "dell",
    "os_pass": "calvin",
    "idrac_ip": "192.168.1.101",
    "idrac_user": "root",
    "idrac_pass": "calvin"
  }'

# 3. Run sanity check
curl -X POST http://localhost:8001/api/sanity_check

# 4. Start test
curl -X POST http://localhost:8001/api/test/start \
  -H "Content-Type: application/json" \
  -d '{
    "phase_duration": 30,
    "rest_duration": 10,
    "config_id": 1
  }'

# 5. Monitor status
curl http://localhost:8001/api/test/status

# 6. Generate report
curl -X POST http://localhost:8001/api/report/generate

# 7. Download report
curl http://localhost:8001/api/report/download/20260302_162939 \
  -o report.xlsx
```

---

*For WebSocket integration examples, see the Frontend Architecture documentation.*

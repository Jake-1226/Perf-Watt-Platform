# Report Generation Architecture

The report generation system creates comprehensive Excel workbooks with multiple sheets, charts, and detailed analysis of benchmark test results.

## Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                    Report Generation Pipeline                        │
│                                                                      │
│  Per-Run SQLite DB           Report Generator           Excel Workbook │
│  ┌─────────────────┐         ┌─────────────────┐      ┌─────────────┐ │
│  │ os_metrics      │ ───────► │ 7-Sheet Builder │ ─────► │ .xlsx File  │ │
│  │ power_metrics   │         │                 │      │             │ │
│  │ benchmark_events│         │ • Summary       │      │ • Charts    │ │
│  │ system_info     │         │ • Raw Data      │      │ • Tables    │ │
│  └─────────────────┘         │ • Aggregations  │      │ • Formatting│ │
│                                │ • Charts        │      │             │ │
│                                └─────────────────┘      └─────────────┘ │
│                                                                      │
│  Additional Exports                                                   │
│  ┌─────────────────┐         ┌─────────────────┐                     │
│  │ os_metrics.csv  │         │ power_metrics.csv│                     │
│  │ (Flat export)   │         │ (Flat export)   │                     │
│  └─────────────────┘         └─────────────────┘                     │
└──────────────────────────────────────────────────────────────────────┘
```

## Excel Workbook Structure

The generated Excel workbook contains 7 sheets with comprehensive analysis:

### Sheet 1: Summary

**Purpose**: High-level overview and system configuration

**Contents**:
- Test metadata (run ID, generation timestamp)
- System information table (OS, CPU, memory, BIOS details)
- Per-phase performance comparison table
- Overall statistics (duration, sample counts, power ranges)

**Key Metrics Table**:
| Phase | OS Samples | Avg CPU% | Max CPU% | Avg Mem% | Pwr Samples | Avg AC(W) | Max AC(W) | Avg CPU Pwr(W) |
|-------|------------|-----------|-----------|----------|-------------|-----------|-----------|----------------|
| idle_baseline | 5 | 0.0 | 0.0 | 15.2 | 2 | 180.5 | 185.2 | 45.3 |
| hpl_100pct | 15 | 100.0 | 100.0 | 15.8 | 6 | 450.5 | 465.2 | 120.3 |

### Sheet 2: OS Metrics (Raw)

**Purpose**: Complete time-series data for OS performance metrics

**Columns**:
- `id`, `timestamp`, `epoch`, `phase`
- `cpu_pct`, `mem_pct`, `mem_used_mb`, `mem_total_mb`
- `load_1m`, `load_5m`, `load_15m`
- `disk_read_kbs`, `disk_write_kbs` (reserved)
- `net_rx_kbs`, `net_tx_kbs` (reserved)
- `process_count`, `top_processes` (JSON)

**Sample Data**:
| timestamp | epoch | phase | cpu_pct | mem_pct | mem_used_mb | load_1m | process_count |
|-----------|-------|-------|---------|---------|-------------|----------|---------------|
| 2026-03-02T16:30:00Z | 1709386200.0 | idle_baseline | 0.0 | 15.2 | 78643 | 0.5 | 285 |
| 2026-03-02T16:30:02Z | 1709386202.0 | idle_baseline | 0.1 | 15.2 | 78644 | 0.5 | 286 |

### Sheet 3: Power Metrics (Raw)

**Purpose**: Complete time-series data for power and thermal metrics

**Columns**:
- `id`, `timestamp`, `epoch`, `phase`
- `sys_input_ac_w`, `cpu_power_w`, `dimm_power_w`
- `storage_power_w`, `fan_power_w`
- `inlet_temp_c`, `exhaust_temp_c`, `cpu_temp_c`
- `raw_sensors` (JSON of all parsed sensors)

**Sample Data**:
| timestamp | epoch | phase | sys_input_ac_w | cpu_power_w | dimm_power_w | inlet_temp_c | cpu_temp_c |
|-----------|-------|-------|----------------|-------------|-------------|--------------|------------|
| 2026-03-02T16:30:00Z | 1709386200.0 | idle_baseline | 180.5 | 45.3 | 12.8 | 22.5 | 35.2 |
| 2026-03-02T16:30:05Z | 1709386205.0 | idle_baseline | 182.1 | 46.1 | 13.1 | 22.6 | 35.4 |

### Sheet 4: Phase Summary

**Purpose**: Aggregated statistics per phase for easy comparison

**Columns**:
- `phase`, `duration(s)`, `samples`
- `avg_cpu_pct`, `min_cpu_pct`, `max_cpu_pct`, `avg_mem_pct`
- `avg_ac_w`, `min_ac_w`, `max_ac_w`
- `avg_cpu_w`, `avg_dimm_w`, `avg_storage_w`, `avg_fan_w`

**Sample Data**:
| phase | duration(s) | samples | avg_cpu_pct | max_cpu_pct | avg_mem_pct | avg_ac_w | max_ac_w | avg_cpu_w |
|-------|-------------|---------|-------------|-------------|-------------|----------|----------|----------|
| hpl_100pct | 30.0 | 15 | 100.0 | 100.0 | 15.8 | 450.5 | 465.2 | 120.3 |
| fio_100pct | 30.0 | 15 | 6.8 | 7.2 | 15.9 | 220.8 | 235.1 | 58.2 |

### Sheet 5: System Info

**Purpose**: Complete system information collected during sanity check

**Structure**:
- Collected timestamp
- Source (OS or iDRAC)
- Key-value pairs of system information

**Sample Data**:
| collected_at | source | key | value |
|--------------|--------|-----|-------|
| 2026-03-02T16:29:39Z | os | hostname | test-server |
| 2026-03-02T16:29:39Z | os | cpu_model | Intel Xeon Platinum 8360Y |
| 2026-03-02T16:29:39Z | os | cpu_cores | 96 |
| 2026-03-02T16:29:39Z | idrac | idrac_version | 7.0.0.0 |
| 2026-03-02T16:29:39Z | idrac | service_tag | ABC123 |

### Sheet 6: Benchmark Events

**Purpose**: Timeline of benchmark lifecycle events

**Columns**:
- `timestamp`, `epoch`, `phase`, `event_type`
- `benchmark`, `message`, `data` (JSON)

**Event Types**:
- `sequence_start` - Test sequence begins
- `phase_start` - Individual phase begins
- `phase_end` - Individual phase ends
- `sequence_end` - Test sequence completes

**Sample Data**:
| timestamp | epoch | phase | event_type | benchmark | message |
|-----------|-------|-------|------------|-----------|---------|
| 2026-03-02T16:29:40Z | 1709386180.0 | | sequence_start | | Starting test sequence |
| 2026-03-02T16:29:41Z | 1709386181.0 | 01_idle_baseline | phase_start | Starting phase 01_idle_baseline |
| 2026-03-02T16:29:51Z | 1709386191.0 | 01_idle_baseline | phase_end | Completed phase 01_idle_baseline |

### Sheet 7: Charts

**Purpose**: Visual representation of key metrics over time

**Charts Included**:
1. **CPU Utilization Over Time** - Line chart of CPU% across all phases
2. **Memory Utilization Over Time** - Line chart of memory% across all phases
3. **System AC Power Over Time** - Line chart of total power consumption
4. **CPU Power Over Time** - Line chart of CPU subsystem power

**Chart Configuration**:
```python
# Chart 1: CPU Utilization
chart1 = LineChart()
chart1.title = "CPU Utilization Over Time"
chart1.y_axis.title = "CPU %"
chart1.x_axis.title = "Sample #"
chart1.width = 30
chart1.height = 15
data_ref = Reference(ws_os, min_col=5, min_row=1, max_row=os_count + 1)
chart1.add_data(data_ref, titles_from_data=True)
ws_charts.add_chart(chart1, "A1")
```

## Report Generation Process

### Generation Workflow

```python
def generate_excel_report(db_path: str, output_path: str, run_metadata: dict = None):
    """Generate a comprehensive Excel report from telemetry data."""
    wb = Workbook()

    # 1. Summary sheet
    ws_summary = wb.active
    ws_summary.title = "Summary"
    _write_summary_sheet(ws_summary, db_path, run_metadata or {})

    # 2. OS Metrics sheet
    ws_os = wb.create_sheet("OS Metrics")
    _write_os_metrics_sheet(ws_os, db_path)

    # 3. Power Metrics sheet
    ws_power = wb.create_sheet("Power Metrics")
    _write_power_metrics_sheet(ws_power, db_path)

    # 4. Phase Summary sheet
    ws_phases = wb.create_sheet("Phase Summary")
    _write_phase_summary_sheet(ws_phases, db_path)

    # 5. System Info sheet
    ws_sysinfo = wb.create_sheet("System Info")
    _write_sysinfo_sheet(ws_sysinfo, db_path)

    # 6. Benchmark Events sheet
    ws_events = wb.create_sheet("Benchmark Events")
    _write_events_sheet(ws_events, db_path)

    # 7. Charts sheet
    ws_charts = wb.create_sheet("Charts")
    _write_charts_sheet(ws_charts, ws_os, ws_power, db_path)

    wb.save(output_path)
    return output_path
```

### Data Aggregation Logic

**Phase Summary Aggregation**:
```python
def _write_phase_summary_sheet(ws, db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # OS metrics by phase
    c.execute("""
        SELECT phase,
            MAX(epoch)-MIN(epoch) as dur, COUNT(*),
            AVG(cpu_pct), MIN(cpu_pct), MAX(cpu_pct), AVG(mem_pct)
        FROM os_metrics WHERE phase != '' GROUP BY phase ORDER BY MIN(epoch)
    """)
    os_data = {r[0]: r for r in c.fetchall()}

    # Power by phase
    c.execute("""
        SELECT phase, COUNT(*),
            AVG(sys_input_ac_w), MIN(sys_input_ac_w), MAX(sys_input_ac_w),
            AVG(cpu_power_w), AVG(dimm_power_w), AVG(storage_power_w), AVG(fan_power_w)
        FROM power_metrics WHERE phase != '' GROUP BY phase ORDER BY MIN(epoch)
    """)
    pwr_data = {r[0]: r for r in c.fetchall()}

    # Merge and write data
    row = 4
    all_phases = list(dict.fromkeys(list(os_data.keys()) + list(pwr_data.keys())))
    for phase in all_phases:
        os = os_data.get(phase, (phase, 0, 0, None, None, None, None))
        pw = pwr_data.get(phase, (phase, 0, None, None, None, None, None, None, None))
        
        vals = [
            phase,
            round(os[1], 0) if os[1] else 0,
            os[2],
            round(os[3], 1) if os[3] else "N/A",
            round(os[4], 1) if os[4] else "N/A",
            round(os[5], 1) if os[5] else "N/A",
            round(os[6], 1) if os[6] else "N/A",
            round(pw[2], 1) if pw[2] else "N/A",
            round(pw[3], 1) if pw[3] else "N/A",
            round(pw[4], 1) if pw[4] else "N/A",
            round(pw[5], 1) if pw[5] else "N/A",
            round(pw[6], 1) if pw[6] else "N/A",
            round(pw[7], 1) if pw[7] else "N/A",
            round(pw[8], 1) if pw[8] else "N/A",
        ]
        
        for i, v in enumerate(vals, 1):
            cell = ws.cell(row=row, column=i, value=v)
            cell.font = DATA_FONT
            cell.border = THIN_BORDER
        row += 1

    conn.close()
    _auto_width(ws)
```

### Styling and Formatting

**Header Styling**:
```python
HEADER_FONT = Font(bold=True, size=12, color="FFFFFF")
HEADER_FILL = PatternFill(start_color="2F5496", end_color="2F5496", fill_type="solid")
THIN_BORDER = Border(
    left=Side(style="thin"), right=Side(style="thin"),
    top=Side(style="thin"), bottom=Side(style="thin")
)

def _style_header(ws, row, cols):
    for col in range(1, cols + 1):
        cell = ws.cell(row=row, column=col)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center")
        cell.border = THIN_BORDER
```

**Column Auto-Sizing**:
```python
def _auto_width(ws):
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            try:
                if cell.value:
                    max_len = max(max_len, len(str(cell.value)))
            except:
                pass
        ws.column_dimensions[col_letter].width = min(max_len + 3, 40)
```

## CSV Exports

### OS Metrics CSV

```python
def export_os_csv(filepath: str):
    """Export OS metrics to CSV."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM os_metrics ORDER BY epoch ASC")
    rows = c.fetchall()
    
    if not rows:
        conn.close()
        return
    
    keys = rows[0].keys()
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for r in rows:
            writer.writerow(dict(r))
    conn.close()
```

### Power Metrics CSV

```python
def export_power_csv(filepath: str):
    """Export power metrics to CSV."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM power_metrics ORDER BY epoch ASC")
    rows = c.fetchall()
    
    if not rows:
        conn.close()
        return
    
    keys = rows[0].keys()
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for r in rows:
            writer.writerow(dict(r))
    conn.close()
```

## JSON Summary Generation

### Summary Structure

```python
def generate_summary(db_path: str) -> dict:
    """Generate a JSON summary of the test run for the dashboard."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    summary = {"phases": [], "overall": {}, "system_info": {}}

    # Overall statistics
    c.execute("SELECT MIN(epoch), MAX(epoch), COUNT(*) FROM os_metrics")
    r = c.fetchone()
    if r[0] and r[1]:
        summary["overall"]["duration_s"] = round(r[1] - r[0], 0)
        summary["overall"]["os_samples"] = r[2]

    c.execute("SELECT COUNT(*), AVG(sys_input_ac_w), MIN(sys_input_ac_w), MAX(sys_input_ac_w) FROM power_metrics WHERE sys_input_ac_w IS NOT NULL")
    r = c.fetchone()
    summary["overall"]["power_samples"] = r[0]
    if r[1]:
        summary["overall"]["avg_ac_w"] = round(r[1], 1)
        summary["overall"]["min_ac_w"] = round(r[2], 1)
        summary["overall"]["max_ac_w"] = round(r[3], 1)

    # Per-phase statistics
    c.execute("""
        SELECT phase, COUNT(*), AVG(cpu_pct), MIN(cpu_pct), MAX(cpu_pct), AVG(mem_pct)
        FROM os_metrics WHERE phase != '' GROUP BY phase ORDER BY MIN(epoch)
    """)
    os_phases = {r[0]: r for r in c.fetchall()}

    c.execute("""
        SELECT phase, COUNT(*), AVG(sys_input_ac_w), MIN(sys_input_ac_w), MAX(sys_input_ac_w),
        AVG(cpu_power_w), AVG(dimm_power_w), AVG(storage_power_w), AVG(fan_power_w)
        FROM power_metrics WHERE phase != '' GROUP BY phase ORDER BY MIN(epoch)
    """)
    pwr_phases = {r[0]: r for r in c.fetchall()}

    all_phases = list(dict.fromkeys(list(os_phases.keys()) + list(pwr_phases.keys())))
    for phase in all_phases:
        os = os_phases.get(phase)
        pw = pwr_phases.get(phase)
        entry = {"name": phase}
        
        if os:
            entry["os_samples"] = os[1]
            entry["avg_cpu_pct"] = round(os[2], 1) if os[2] else None
            entry["max_cpu_pct"] = round(os[4], 1) if os[4] else None
            entry["avg_mem_pct"] = round(os[5], 1) if os[5] else None
        
        if pw:
            entry["pwr_samples"] = pw[1]
            entry["avg_ac_w"] = round(pw[2], 1) if pw[2] else None
            entry["avg_cpu_w"] = round(pw[5], 1) if pw[5] else None
            entry["avg_dimm_w"] = round(pw[6], 1) if pw[6] else None
            entry["avg_stor_w"] = round(pw[7], 1) if pw[7] else None
            entry["avg_fan_w"] = round(pw[8], 1) if pw[8] else None
        
        summary["phases"].append(entry)

    # System information
    c.execute("SELECT source, key, value FROM system_info")
    for r in c.fetchall():
        src = r[0]
        if src not in summary["system_info"]:
            summary["system_info"][src] = {}
        summary["system_info"][src][r[1]] = r[2]

    conn.close()
    return summary
```

**Sample JSON Output**:
```json
{
  "phases": [
    {
      "name": "02_hpl_100pct",
      "os_samples": 15,
      "avg_cpu_pct": 100.0,
      "max_cpu_pct": 100.0,
      "avg_mem_pct": 15.8,
      "pwr_samples": 6,
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
  },
  "system_info": {
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

## File Management

### Report File Naming

```
data/<run_id>/report_<run_id>.xlsx
Example: data/20260302_162939/report_20260302_162939.xlsx
```

### CSV File Naming

```
data/<run_id>/os_metrics.csv
data/<run_id>/power_metrics.csv
```

### Storage Requirements

| File Type | Typical Size | 30-min Test | 1-hour Test |
|-----------|--------------|--------------|--------------|
| Excel Report | 2-5 MB | ~3 MB | ~5 MB |
| OS Metrics CSV | 1-2 MB | ~1.5 MB | ~2.5 MB |
| Power Metrics CSV | 0.5-1 MB | ~0.8 MB | ~1.2 MB |
| Telemetry DB | 2-3 MB | ~2.5 MB | ~4 MB |
| **Total** | **5-10 MB** | **~8 MB** | **~13 MB** |

## Performance Considerations

### Generation Time

| Test Duration | Report Generation Time | CSV Export Time |
|--------------|------------------------|-----------------|
| 15 minutes | ~2-3 seconds | ~1 second |
| 30 minutes | ~4-5 seconds | ~2 seconds |
| 1 hour | ~8-10 seconds | ~3 seconds |

### Memory Usage

- **Excel workbook**: ~10-20 MB in memory during generation
- **Database queries**: ~5-10 MB for result sets
- **CSV generation**: ~2-5 MB for data buffering

### Optimization Techniques

```python
# Use row_factory for memory efficiency
conn.row_factory = sqlite3.Row

# Process results in batches for large datasets
def process_in_batches(query, batch_size=1000):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(query)
    
    while True:
        rows = c.fetchmany(batch_size)
        if not rows:
            break
        yield rows
    
    conn.close()

# Use generators for memory-efficient CSV writing
def write_csv_generator(filepath, query):
    with open(filepath, "w", newline="") as f:
        writer = None
        for batch in process_in_batches(query):
            if writer is None:
                writer = csv.DictWriter(f, fieldnames=batch[0].keys())
                writer.writeheader()
            for row in batch:
                writer.writerow(dict(row))
```

## Error Handling

### Common Generation Errors

```python
# Database access errors
try:
    conn = sqlite3.connect(db_path)
    # ... operations ...
except sqlite3.Error as e:
    raise ReportGenerationError(f"Database error: {e}")
finally:
    if 'conn' in locals():
        conn.close()

# File system errors
try:
    wb.save(output_path)
except PermissionError:
    raise ReportGenerationError(f"Permission denied: {output_path}")
except Exception as e:
    raise ReportGenerationError(f"Failed to save report: {e}")

# Data validation errors
if not os.path.exists(db_path):
    raise ReportGenerationError("Telemetry database not found")

if os.path.getsize(db_path) == 0:
    raise ReportGenerationError("Telemetry database is empty")
```

### Validation Checks

```python
def validate_telemetry_data(db_path):
    """Validate telemetry data before report generation."""
    conn = sqlite3.connect(db_path)
    
    # Check required tables exist
    required_tables = ['os_metrics', 'power_metrics', 'benchmark_events']
    for table in required_tables:
        result = conn.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'").fetchone()
        if not result:
            raise ReportGenerationError(f"Missing required table: {table}")
    
    # Check data availability
    os_count = conn.execute("SELECT COUNT(*) FROM os_metrics").fetchone()[0]
    power_count = conn.execute("SELECT COUNT(*) FROM power_metrics").fetchone()[0]
    
    if os_count == 0 and power_count == 0:
        raise ReportGenerationError("No telemetry data available")
    
    conn.close()
```

---

*For the complete implementation details, see `backend/reports.py` in the source code.*

"""Quick end-to-end test: connect, start short test, poll, generate report."""
import json
import time
from urllib.request import urlopen, Request

API = "http://localhost:8001"

def api_post(path, data=None):
    body = json.dumps(data or {}).encode()
    req = Request(f"{API}{path}", data=body,
                  headers={"Content-Type": "application/json"}, method="POST")
    return json.loads(urlopen(req, timeout=60).read())

def api_get(path):
    return json.loads(urlopen(f"{API}{path}", timeout=10).read())

# 1. Connect
print("=== CONNECTING ===")
result = api_post("/api/connect", {
    "os_ip": "100.71.148.76", "os_user": "dell", "os_pass": "calvin",
    "idrac_ip": "100.71.148.195", "idrac_user": "root", "idrac_pass": "calvin"
})
print(f"  OS: {result['os']['status']}, iDRAC: {result['idrac']['status']}")

# 2. Sanity check
print("\n=== SANITY CHECK ===")
sanity = api_post("/api/sanity_check")
sysinfo = sanity.get("os", {}).get("sysinfo", {})
print(f"  Hostname: {sysinfo.get('hostname')}")
print(f"  CPU: {sysinfo.get('cpu_model')} ({sysinfo.get('cpu_cores')} cores)")
print(f"  Memory: {sysinfo.get('memory_total_gb')} GB")
thmtest = sanity.get("idrac", {}).get("thmtest_sample", {})
print(f"  Power: AC={thmtest.get('SYS_PWR_INPUT_AC', 'N/A')}W, CPU={thmtest.get('CPU_PWR_ALL', 'N/A')}W")
caps = sanity.get("capabilities", {})
missing = [k for k, v in caps.items() if not v]
print(f"  Tools OK: {sum(caps.values())}/{len(caps)}, missing: {missing or 'none'}")

# 3. Start short test
print("\n=== STARTING SHORT TEST (idle 15s → stress 20s → idle 15s) ===")
result = api_post("/api/test/start", {
    "phase_duration": 20,
    "rest_duration": 5,
    "phases": [
        {"name": "01_idle_baseline", "type": "idle", "duration": 15},
        {"name": "02_stress_cpu", "type": "stress_ng", "duration": 20, "cores": 8, "stressor": "cpu"},
        {"name": "03_idle_cooldown", "type": "idle", "duration": 15},
    ]
})
run_id = result.get("run_id", "unknown")
print(f"  Run ID: {run_id}")

# 4. Poll status — wait longer to allow dep install
print("\n=== MONITORING (deps install may take ~60s first) ===")
max_cpu = 0.0
idle_cpus = []
stress_cpus = []
for i in range(60):
    time.sleep(3)
    status = api_get("/api/test/status")
    latest = api_get("/api/telemetry/latest")
    os_data = latest.get("os", {})
    pwr_data = latest.get("power", {})
    cpu_pct = os_data.get("cpu_pct", "N/A")
    mem_pct = os_data.get("mem_pct", "N/A")
    ac_w = pwr_data.get("SYS_PWR_INPUT_AC", "N/A")
    cpu_w = pwr_data.get("CPU_PWR_ALL", "N/A")
    phase = status.get("current_phase", "?")
    running = status.get("running", False)
    elapsed = (i + 1) * 3
    # Track CPU by phase
    if isinstance(cpu_pct, (int, float)):
        if cpu_pct > max_cpu:
            max_cpu = cpu_pct
        if 'idle' in phase:
            idle_cpus.append(cpu_pct)
        elif 'stress' in phase:
            stress_cpus.append(cpu_pct)
    print(f"  [{elapsed:3d}s] phase={phase:<25s} cpu={str(cpu_pct):>6s}% mem={str(mem_pct):>6s}% | AC={str(ac_w):>7s}W CPU_pwr={str(cpu_w):>7s}W")
    if not running and elapsed > 30:
        break

# 5. Check collected data
# Quick validation
print("\n=== VALIDATION ===")
avg_idle_cpu = sum(idle_cpus) / len(idle_cpus) if idle_cpus else -1
avg_stress_cpu = sum(stress_cpus) / len(stress_cpus) if stress_cpus else -1
print(f"  Max CPU%: {max_cpu:.1f}")
print(f"  Avg idle CPU%: {avg_idle_cpu:.1f}")
print(f"  Avg stress CPU%: {avg_stress_cpu:.1f}")
if avg_stress_cpu > avg_idle_cpu and avg_stress_cpu > 1.0:
    print("  PASS: CPU% rises during stress phase")
else:
    print("  WARN: CPU% did not rise significantly during stress phase")

print("\n=== DATA CHECK ===")
os_tel = api_get("/api/telemetry/os?limit=500")
pwr_tel = api_get("/api/telemetry/power?limit=500")
events = api_get("/api/telemetry/events")
print(f"  OS metric samples: {len(os_tel.get('data', []))}")
print(f"  Power metric samples: {len(pwr_tel.get('data', []))}")
print(f"  Benchmark events: {len(events.get('data', []))}")

# 6. Generate report
print("\n=== GENERATING REPORT ===")
report = api_post("/api/report/generate")
summary = report.get("summary", {})
print(f"  Status: {report.get('status')}")
print(f"  Excel: {report.get('excel_path')}")
overall = summary.get("overall", {})
print(f"  Duration: {overall.get('duration_s', 0):.0f}s")
print(f"  Avg AC Power: {overall.get('avg_ac_w', 'N/A')}W")
print(f"  Phases:")
for p in summary.get("phases", []):
    print(f"    {p['name']}: cpu={p.get('avg_cpu_pct', 'N/A')}%, ac={p.get('avg_ac_w', 'N/A')}W")

# 7. Check runs
print("\n=== PAST RUNS ===")
runs = api_get("/api/runs")
for r in runs.get("runs", []):
    print(f"  {r['run_id']}: report={r['has_report']}, os_csv={r['has_os_csv']}, pwr_csv={r['has_power_csv']}")

print("\n=== TEST COMPLETE ===")

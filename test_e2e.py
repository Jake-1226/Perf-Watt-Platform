"""
End-to-end test: validates every stage of the platform.
1. API health check
2. Save config
3. Load config
4. Connect
5. Sanity check
6. Start HPL+FIO test (short)
7. Monitor telemetry via polling
8. Generate report
9. Verify run history
"""
import json
import sys
import time
from urllib.request import urlopen, Request
from urllib.error import HTTPError

API = "http://localhost:8001"
PASS = 0
FAIL = 0

def api(method, path, data=None):
    url = API + path
    body = json.dumps(data).encode() if data else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = Request(url, data=body, headers=headers, method=method)
    try:
        r = urlopen(req, timeout=120)
        return json.loads(r.read()), r.status
    except HTTPError as e:
        return {"error": e.read().decode()}, e.code

def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name} -- {detail}")

print("=" * 60)
print("FULL END-TO-END TEST")
print("=" * 60)

# 1. Health check
print("\n--- Stage 1: API Health ---")
d, code = api("GET", "/api/connection_status")
check("API responds", code == 200)
check("Returns connection status", "os_connected" in d)

# 2. Save config
print("\n--- Stage 2: Save Config ---")
d, code = api("POST", "/api/configs", {
    "name": "e2e-test-server",
    "os_ip": "100.71.148.76", "os_user": "dell", "os_pass": "calvin",
    "idrac_ip": "100.71.148.195", "idrac_user": "root", "idrac_pass": "calvin",
    "notes": "E2E test config"
})
check("Save config returns 200", code == 200)
check("Config ID returned", "config_id" in d, str(d))
config_id = d.get("config_id")

# 3. List and load configs
print("\n--- Stage 3: List & Load Configs ---")
d, code = api("GET", "/api/configs")
check("List configs OK", code == 200)
configs = d.get("configs", [])
check("Has saved configs", len(configs) > 0, f"got {len(configs)}")
found = any(c["name"] == "e2e-test-server" for c in configs)
check("Our config exists", found)

if config_id:
    d, code = api("GET", f"/api/configs/{config_id}")
    check("Load config by ID", code == 200)
    check("Config has correct IP", d.get("os_ip") == "100.71.148.76")

# 4. Connect
print("\n--- Stage 4: Connect ---")
d, code = api("POST", "/api/connect", {
    "os_ip": "100.71.148.76", "os_user": "dell", "os_pass": "calvin",
    "idrac_ip": "100.71.148.195", "idrac_user": "root", "idrac_pass": "calvin",
    "config_id": config_id
})
check("Connect returns 200", code == 200)
os_ok = d.get("os", {}).get("status") == "connected"
idrac_ok = d.get("idrac", {}).get("status") == "connected"
check("OS connected", os_ok, str(d.get("os")))
check("iDRAC connected", idrac_ok, str(d.get("idrac")))

if not os_ok:
    print("\nCANNOT CONTINUE: OS not connected")
    sys.exit(1)

# 5. Sanity check
print("\n--- Stage 5: Sanity Check ---")
url = f"/api/sanity_check?config_id={config_id}" if config_id else "/api/sanity_check"
d, code = api("POST", url)
check("Sanity check returns 200", code == 200)
check("Has OS sysinfo", "sysinfo" in d.get("os", {}))
check("Has capabilities", len(d.get("capabilities", {})) > 0)
hostname = d.get("os", {}).get("sysinfo", {}).get("hostname", "")
cores = d.get("os", {}).get("sysinfo", {}).get("cpu_cores", "0")
check("Got hostname", len(hostname) > 0, hostname)
check("Got CPU cores", int(cores) > 0, cores)

if idrac_ok:
    check("Has iDRAC power", "thmtest_sample" in d.get("idrac", {}))
    ac = d.get("idrac", {}).get("thmtest_sample", {}).get("SYS_PWR_INPUT_AC", 0)
    check("AC power > 0", ac > 0, f"AC={ac}")

# Check sanity persisted
if config_id:
    d2, _ = api("GET", f"/api/configs/{config_id}/sanity")
    check("Sanity persisted to DB", d2.get("sanity") is not None)

# Verify caps include HPL build tools
caps = d.get("capabilities", {})
check("gcc available", caps.get("gcc", False))
check("mpicc available", caps.get("mpicc", False))
check("fio available", caps.get("fio", False))

# 6. Start test (short HPL + FIO test, 15s phases)
print("\n--- Stage 6: Start Test (HPL+FIO, 15s phases) ---")
d, code = api("POST", "/api/test/start", {
    "phase_duration": 15,
    "rest_duration": 5,
    "phases": [
        {"name": "01_idle", "type": "idle", "duration": 10},
        {"name": "02_hpl_full", "type": "hpl_100", "duration": 15},
        {"name": "03_fio_full", "type": "fio_100", "duration": 15},
        {"name": "04_idle_end", "type": "idle", "duration": 10},
    ],
    "config_id": config_id
})
check("Start test returns 200", code == 200, str(d))
run_id = d.get("run_id", "")
check("Got run_id", len(run_id) > 0, run_id)
check("Test status=started", d.get("status") == "started")

# 7. Monitor
print("\n--- Stage 7: Monitor Test ---")
max_wait = 180  # 3 minutes max
start = time.time()
samples = 0
last_phase = ""
while time.time() - start < max_wait:
    d, _ = api("GET", "/api/test/status")
    running = d.get("running", False)
    phase = d.get("current_phase", "")
    if phase != last_phase:
        print(f"  Phase: {phase}")
        last_phase = phase
    if not running and phase in ("complete", "none"):
        break

    # Check telemetry
    d2, _ = api("GET", "/api/telemetry/latest")
    cpu = d2.get("os", {}).get("cpu_pct")
    ac = d2.get("power", {}).get("SYS_PWR_INPUT_AC")
    if cpu is not None:
        samples += 1
    time.sleep(5)

elapsed = time.time() - start
check("Test completed within timeout", elapsed < max_wait, f"elapsed={elapsed:.0f}s")
check("Got telemetry samples", samples > 0, f"samples={samples}")

# Verify test status
d, _ = api("GET", "/api/test/status")
check("Test not running", not d.get("running", True))
check("Phase is complete", d.get("current_phase") in ("complete", "none"))

# Check logs
d, _ = api("GET", "/api/test/logs?limit=10")
check("Got log lines", len(d.get("lines", [])) > 0, f"lines={len(d.get('lines', []))}")

# 8. Generate report
print("\n--- Stage 8: Generate Report ---")
d, code = api("POST", "/api/report/generate")
check("Report generation OK", code == 200, str(d)[:200])
check("Report has summary", "summary" in d)
check("Summary has phases", len(d.get("summary", {}).get("phases", [])) > 0)
check("Summary has overall", "avg_ac_w" in d.get("summary", {}).get("overall", {}))

# Verify report download
try:
    req = Request(f"{API}/api/report/download/{run_id}")
    r = urlopen(req, timeout=10)
    size = len(r.read())
    check("Report downloadable", size > 1000, f"size={size}")
except Exception as e:
    check("Report downloadable", False, str(e))

# 9. Run history
print("\n--- Stage 9: Run History ---")
d, code = api("GET", "/api/runs")
check("List runs OK", code == 200)
runs = d.get("runs", [])
check("Has runs", len(runs) > 0, f"count={len(runs)}")
our_run = next((r for r in runs if r["run_id"] == run_id), None)
check("Our run in history", our_run is not None)
if our_run:
    check("Run has report", our_run.get("has_report", False))
    check("Run status completed", our_run.get("status") in ("completed",))

# Run detail
if run_id:
    d, code = api("GET", f"/api/runs/{run_id}")
    check("Run detail OK", code == 200)
    check("Run has phases", len(d.get("phases", [])) > 0)
    check("Run has os_sysinfo", len(d.get("os_sysinfo", {})) > 0)

# 10. Cleanup: delete test config
print("\n--- Stage 10: Cleanup ---")
if config_id:
    d, code = api("DELETE", f"/api/configs/{config_id}")
    check("Delete config OK", code == 200)

# Summary
print("\n" + "=" * 60)
print(f"RESULTS: {PASS} passed, {FAIL} failed out of {PASS + FAIL} checks")
print("=" * 60)
if FAIL > 0:
    print("SOME CHECKS FAILED - see above")
    sys.exit(1)
else:
    print("ALL CHECKS PASSED")
    sys.exit(0)

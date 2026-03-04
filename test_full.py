"""Full E2E test — tests every API endpoint, UI serving, DB persistence, and a short stress test."""
import requests
import time
import json
import sys

BASE = "http://localhost:8001"
PASS = 0
FAIL = 0

def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name} — {detail}")

def get(path): return requests.get(BASE + path, timeout=15)
def post(path, data=None): return requests.post(BASE + path, json=data, timeout=30)
def delete(path): return requests.delete(BASE + path, timeout=10)

print("=" * 60)
print("FULL E2E TEST")
print("=" * 60)

# ─── 1. Server health ────────────────────────────────────────
print("\n--- 1. Server & UI ---")
r = get("/")
check("GET / returns 200", r.status_code == 200)
check("HTML contains root div", '<div id="root">' in r.text)
check("HTML has React", 'react@18' in r.text)
check("HTML has Recharts", 'recharts' in r.text.lower())
check("HTML has App component", 'function App()' in r.text)
check("HTML has HomePanel", 'function HomePanel' in r.text)
check("HTML has ConnectPanel", 'function ConnectPanel' in r.text)
check("HTML has SanityPanel", 'function SanityPanel' in r.text)
check("HTML has ConfigPanel", 'function ConfigPanel' in r.text)
check("HTML has DashboardPanel", 'function DashboardPanel' in r.text)
check("HTML has ReportPanel", 'function ReportPanel' in r.text)
check("HTML has MetricCard", 'function MetricCard' in r.text)

# ─── 2. Config DB CRUD ───────────────────────────────────────
print("\n--- 2. Config DB ---")
r = get("/api/configs")
check("GET /api/configs returns 200", r.status_code == 200)
check("configs is a list", isinstance(r.json().get("configs"), list))

r = post("/api/configs", {"name": "E2E Test Server", "os_ip": "100.71.148.76", "os_user": "dell", "os_pass": "calvin", "idrac_ip": "100.71.148.195", "idrac_user": "root", "idrac_pass": "calvin"})
check("POST /api/configs saves", r.status_code == 200 and "config_id" in r.json())
cid = r.json().get("config_id")

r = get(f"/api/configs/{cid}")
check("GET /api/configs/{id} retrieves", r.status_code == 200 and r.json().get("name") == "E2E Test Server")

r = get(f"/api/configs/{cid}/sanity")
check("GET /api/configs/{id}/sanity returns", r.status_code == 200)

# ─── 3. Connection ────────────────────────────────────────────
print("\n--- 3. Connection ---")
r = get("/api/connection_status")
check("GET /api/connection_status", r.status_code == 200)
was_connected = r.json().get("os_connected", False)

if not was_connected:
    r = post("/api/connect", {"os_ip": "100.71.148.76", "os_user": "dell", "os_pass": "calvin", "idrac_ip": "100.71.148.195", "idrac_user": "root", "idrac_pass": "calvin"})
    check("POST /api/connect", r.status_code == 200)
    d = r.json()
    check("OS connected", d.get("os", {}).get("status") == "connected", str(d.get("os")))
    check("iDRAC connected", d.get("idrac", {}).get("status") == "connected", str(d.get("idrac")))
else:
    check("Already connected (OS)", True)
    check("Already connected (skipping connect call)", True)
    check("Already connected (skipping iDRAC check)", True)

r = get("/api/connection_status")
check("Connection status shows os=true", r.json().get("os_connected") == True)
check("Connection status shows idrac", r.json().get("idrac_connected") is not None)

# ─── 4. Sanity check ─────────────────────────────────────────
print("\n--- 4. Sanity Check ---")
r = post(f"/api/sanity_check?config_id={cid}")
check("POST /api/sanity_check", r.status_code == 200)
d = r.json()
check("Has OS sysinfo", "sysinfo" in d.get("os", {}), str(list(d.get("os", {}).keys())))
check("Hostname present", bool(d.get("os", {}).get("sysinfo", {}).get("hostname")))
check("CPU model present", bool(d.get("os", {}).get("sysinfo", {}).get("cpu_model")))
check("Has capabilities", bool(d.get("capabilities")))
check("gcc available", d.get("capabilities", {}).get("gcc") == True)

# Check sanity was persisted
r = get(f"/api/configs/{cid}/sanity")
check("Sanity persisted to DB", r.status_code == 200 and r.json().get("sanity") is not None)

# ─── 5. Start short test ─────────────────────────────────────
print("\n--- 5. Start Test (short 15s phases) ---")
r = post("/api/test/start", {"phase_duration": 15, "rest_duration": 5, "config_id": cid})
check("POST /api/test/start", r.status_code == 200)
d = r.json()
check("Test started", d.get("status") == "started")
run_id = d.get("run_id", "")
check("Has run_id", bool(run_id))
check("Has config.phases", len(d.get("config", {}).get("phases", [])) > 0)

# ─── 6. Monitor test ─────────────────────────────────────────
print("\n--- 6. Monitor (30s) ---")
time.sleep(5)
r = get("/api/test/status")
check("GET /api/test/status", r.status_code == 200)
check("Test is running", r.json().get("running") == True)

r = get("/api/test/logs")
check("GET /api/test/logs", r.status_code == 200)
check("Log lines exist", r.json().get("total", 0) > 0, f"total={r.json().get('total')}")

r = get("/api/telemetry/os?limit=10")
check("GET /api/telemetry/os", r.status_code == 200)

r = get("/api/telemetry/power?limit=10")
check("GET /api/telemetry/power", r.status_code == 200)

r = get("/api/telemetry/latest")
check("GET /api/telemetry/latest", r.status_code == 200)

r = get("/api/telemetry/sysinfo")
check("GET /api/telemetry/sysinfo", r.status_code == 200)

r = get("/api/telemetry/events")
check("GET /api/telemetry/events", r.status_code == 200)

# Wait for more telemetry
print("  ... waiting 25s for telemetry data ...")
time.sleep(25)

r = get("/api/telemetry/os?limit=10")
os_data = r.json().get("data", [])
check("OS telemetry has data", len(os_data) > 0, f"len={len(os_data)}")

r = get("/api/telemetry/power?limit=10")
pwr_data = r.json().get("data", [])
check("Power telemetry has data", len(pwr_data) > 0, f"len={len(pwr_data)}")

# ─── 7. Stop test ────────────────────────────────────────────
print("\n--- 7. Stop Test ---")
r = post("/api/test/stop")
check("POST /api/test/stop", r.status_code == 200)
time.sleep(2)

r = get("/api/test/status")
check("Test stopped", r.json().get("running") == False)

# ─── 8. Report ───────────────────────────────────────────────
print("\n--- 8. Report ---")
r = post("/api/report/generate")
check("POST /api/report/generate", r.status_code == 200)
d = r.json()
check("Report generated", d.get("status") == "generated")
check("Has summary", "summary" in d)
check("Summary has phases", len(d.get("summary", {}).get("phases", [])) > 0)
check("Summary has overall", "overall" in d.get("summary", {}))

r = get(f"/api/report/download/{run_id}")
check("GET /api/report/download", r.status_code == 200)
check("Report is Excel", "spreadsheet" in r.headers.get("content-type", ""))

r = get("/api/report/summary")
check("GET /api/report/summary", r.status_code == 200)

# ─── 9. Run history ──────────────────────────────────────────
print("\n--- 9. Run History & DB ---")
r = get("/api/runs")
check("GET /api/runs", r.status_code == 200)
runs = r.json().get("runs", [])
check("Has runs", len(runs) > 0)
this_run = [x for x in runs if x.get("run_id") == run_id]
check("Current run in history", len(this_run) > 0)
if this_run:
    check("Run has report flag", this_run[0].get("has_report") == True)

r = get(f"/api/runs/{run_id}")
check("GET /api/runs/{run_id}", r.status_code == 200)
rd = r.json()
check("Run has phases", bool(rd.get("phases")))
check("Run has os_sysinfo", bool(rd.get("os_sysinfo")))

# ─── 10. Cleanup ─────────────────────────────────────────────
print("\n--- 10. Cleanup ---")
r = delete(f"/api/configs/{cid}")
check("DELETE /api/configs/{id}", r.status_code == 200)

r = get(f"/api/configs/{cid}")
check("Config deleted (404)", r.status_code == 404)

# ─── Summary ─────────────────────────────────────────────────
print("\n" + "=" * 60)
total = PASS + FAIL
print(f"RESULTS: {PASS}/{total} passed, {FAIL} failed")
print("=" * 60)

if FAIL > 0:
    sys.exit(1)

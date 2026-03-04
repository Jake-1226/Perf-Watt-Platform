"""Start a quick stress test and verify WebSocket broadcasts live telemetry."""
import asyncio
import json
import time
import threading
from urllib.request import urlopen, Request
import websockets

API = "http://localhost:8001"
WS_MSGS = []

def api_post(path, data=None):
    body = json.dumps(data or {}).encode()
    req = Request(f"{API}{path}", data=body,
                  headers={"Content-Type": "application/json"}, method="POST")
    return json.loads(urlopen(req, timeout=60).read())

async def ws_listener():
    """Listen for WS messages for 30 seconds."""
    uri = "ws://localhost:8001/ws"
    async with websockets.connect(uri) as ws:
        start = time.time()
        while time.time() - start < 35:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=2)
                d = json.loads(msg)
                WS_MSGS.append(d)
                mtype = d.get("type", "?")
                if mtype == "telemetry":
                    cpu = d.get("os", {}).get("cpu_pct", "?")
                    ac = d.get("power", {}).get("SYS_PWR_INPUT_AC", "?")
                    phase = d.get("phase", "?")
                    print(f"  WS telemetry: cpu={cpu}% ac={ac}W phase={phase}")
                elif mtype == "log":
                    line = d.get("line", "")[:60]
                    print(f"  WS log: {line}")
            except asyncio.TimeoutError:
                pass

def run_ws():
    asyncio.run(ws_listener())

# 1. Connect
print("=== Connecting ===")
api_post("/api/connect", {
    "os_ip": "100.71.148.76", "os_user": "dell", "os_pass": "calvin",
    "idrac_ip": "100.71.148.195", "idrac_user": "root", "idrac_pass": "calvin"
})

# 2. Start WS listener in background
ws_thread = threading.Thread(target=run_ws, daemon=True)
ws_thread.start()
time.sleep(1)

# 3. Start a quick 15s stress test
print("=== Starting 15s stress test ===")
api_post("/api/test/start", {
    "phase_duration": 15,
    "rest_duration": 3,
    "phases": [
        {"name": "quick_stress", "type": "stress_ng", "duration": 15, "cores": 16, "stressor": "cpu"},
    ]
})

# 4. Wait for test + WS messages
ws_thread.join(timeout=40)

# 5. Summary
tel_msgs = [m for m in WS_MSGS if m.get("type") == "telemetry"]
log_msgs = [m for m in WS_MSGS if m.get("type") == "log"]
print(f"\n=== WS SUMMARY ===")
print(f"  Telemetry messages: {len(tel_msgs)}")
print(f"  Log messages: {len(log_msgs)}")
if tel_msgs:
    cpus = [m.get("os", {}).get("cpu_pct", 0) for m in tel_msgs if isinstance(m.get("os", {}).get("cpu_pct"), (int, float))]
    acs = [m.get("power", {}).get("SYS_PWR_INPUT_AC", 0) for m in tel_msgs if isinstance(m.get("power", {}).get("SYS_PWR_INPUT_AC"), (int, float))]
    if cpus:
        print(f"  CPU% range: {min(cpus):.1f} - {max(cpus):.1f}")
    if acs:
        print(f"  AC Power range: {min(acs):.1f} - {max(acs):.1f}W")
    print("  PASS: WebSocket broadcasting telemetry during test" if len(tel_msgs) >= 3 else "  FAIL: Too few telemetry messages")
else:
    print("  FAIL: No telemetry messages received via WebSocket")

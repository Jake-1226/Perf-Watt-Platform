"""
Performance Test Platform — FastAPI Backend
Runs locally, connects to remote servers via SSH (paramiko).
Provides REST API + WebSocket for real-time telemetry streaming.
Persistent config DB for saved server profiles and run history.
"""

import asyncio
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .ssh_manager import SSHManager
from . import telemetry
from . import config_db
from .benchmarks import BenchmarkOrchestrator
from .reports import generate_excel_report, generate_summary

app = FastAPI(title="Performance Test Platform", version="3.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# Init persistent config DB
config_db.init(str(DATA_DIR))

# Global state
_executor = ThreadPoolExecutor(max_workers=4)
ssh = SSHManager()
orchestrator: Optional[BenchmarkOrchestrator] = None
inbound_collector: Optional[telemetry.InboundCollector] = None
outbound_collector: Optional[telemetry.OutboundCollector] = None
ws_clients: list[WebSocket] = []
current_run_id: Optional[str] = None
current_run_dir: Optional[Path] = None
current_config_id: Optional[int] = None
stored_os_pass: str = ""

# ─── Pydantic models ─────────────────────────────────────────────────────────

class ConnectRequest(BaseModel):
    os_ip: str
    os_user: str = "dell"
    os_pass: str = "calvin"
    idrac_ip: str = ""
    idrac_user: str = "root"
    idrac_pass: str = "calvin"
    config_id: Optional[int] = None
    save_as: Optional[str] = None

class TestConfig(BaseModel):
    phase_duration: int = 30
    rest_duration: int = 10
    phases: list[dict] = []
    config_id: Optional[int] = None

class SaveConfigRequest(BaseModel):
    name: str
    os_ip: str
    os_user: str = "dell"
    os_pass: str = ""
    idrac_ip: str = ""
    idrac_user: str = "root"
    idrac_pass: str = ""
    notes: str = ""

# ─── Static files ────────────────────────────────────────────────────────────

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/", response_class=HTMLResponse)
async def index():
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return HTMLResponse(index_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Performance Test Platform</h1><p>Static files not found</p>")

# ─── Config endpoints ────────────────────────────────────────────────────────

@app.get("/api/configs")
async def list_configs():
    """List all saved server configurations."""
    return {"configs": config_db.list_configs()}

@app.post("/api/configs")
async def save_config(req: SaveConfigRequest):
    """Save a new server configuration."""
    cid = config_db.save_config(
        name=req.name, os_ip=req.os_ip, os_user=req.os_user, os_pass=req.os_pass,
        idrac_ip=req.idrac_ip, idrac_user=req.idrac_user, idrac_pass=req.idrac_pass,
        notes=req.notes)
    return {"config_id": cid, "status": "saved"}

@app.get("/api/configs/{config_id}")
async def get_config(config_id: int):
    """Get a saved config by ID."""
    cfg = config_db.get_config(config_id)
    if not cfg:
        raise HTTPException(404, "Config not found")
    return cfg

@app.delete("/api/configs/{config_id}")
async def delete_config(config_id: int):
    config_db.delete_config(config_id)
    return {"status": "deleted"}

@app.get("/api/configs/{config_id}/sanity")
async def get_config_sanity(config_id: int):
    """Get latest sanity result for a config."""
    result = config_db.get_latest_sanity(config_id)
    return {"sanity": result}

# ─── Connection endpoints ────────────────────────────────────────────────────

@app.post("/api/connect")
async def connect(req: ConnectRequest):
    """Connect to server OS and optionally iDRAC. Optionally save config."""
    global stored_os_pass, current_config_id
    loop = asyncio.get_event_loop()
    results = {"os": None, "idrac": None}

    os_result = await loop.run_in_executor(
        _executor, partial(ssh.connect_os, req.os_ip, req.os_user, req.os_pass))
    results["os"] = os_result
    if os_result.get("status") == "connected":
        stored_os_pass = req.os_pass

    if req.idrac_ip:
        idrac_result = await loop.run_in_executor(
            _executor, partial(ssh.connect_idrac, req.idrac_ip, req.idrac_user, req.idrac_pass))
        results["idrac"] = idrac_result

    # Save config if requested
    if req.save_as and os_result.get("status") == "connected":
        cid = config_db.save_config(
            name=req.save_as, os_ip=req.os_ip, os_user=req.os_user,
            os_pass=req.os_pass, idrac_ip=req.idrac_ip,
            idrac_user=req.idrac_user, idrac_pass=req.idrac_pass)
        results["config_id"] = cid
        current_config_id = cid
    elif req.config_id:
        current_config_id = req.config_id

    return results

@app.post("/api/disconnect")
async def disconnect():
    _stop_collectors()
    ssh.disconnect_os()
    ssh.disconnect_idrac()
    return {"status": "disconnected"}

@app.get("/api/connection_status")
async def connection_status():
    os_ok = False
    try:
        os_ok = ssh.os_client is not None and ssh.os_client.get_transport() is not None and ssh.os_client.get_transport().is_active()
    except:
        pass
    return {
        "os_connected": os_ok,
        "idrac_connected": ssh.idrac_channel is not None,
    }

# ─── Sanity Check ────────────────────────────────────────────────────────────

@app.post("/api/sanity_check")
async def sanity_check(config_id: Optional[int] = None):
    """Run full sanity check and persist results to config DB."""
    if not ssh.os_client:
        raise HTTPException(400, "OS not connected")

    loop = asyncio.get_event_loop()

    def _do_sanity():
        results = {"os": {}, "idrac": {}, "capabilities": {}}
        try:
            results["os"]["sysinfo"] = ssh.get_os_sysinfo()
        except Exception as e:
            results["os"]["error"] = str(e)

        if ssh.idrac_channel:
            try:
                results["idrac"]["sysinfo"] = ssh.get_idrac_sysinfo()
                raw = ssh.get_thmtest()
                sensors = ssh.parse_thmtest(raw)
                results["idrac"]["thmtest_sample"] = {
                    k: v for k, v in sensors.items()
                    if k in ("SYS_PWR_INPUT_AC", "CPU_PWR_ALL", "DIMM_PWR_ALL",
                             "STORAGE_PWR", "FAN_PWR_MAIN")
                }
                results["idrac"]["thmtest_ok"] = bool(
                    sensors.get("SYS_PWR_INPUT_AC") or sensors.get("CPU_PWR_ALL"))
            except Exception as e:
                results["idrac"]["error"] = str(e)

        caps = {}
        for tool in ["gcc", "gfortran", "mpicc", "mpirun", "fio", "stress-ng", "bc", "wget"]:
            try:
                out, _, rc = ssh.os_exec(f"which {tool} 2>/dev/null", timeout=5)
                caps[tool] = rc == 0
            except:
                caps[tool] = False
        results["capabilities"] = caps
        return results

    results = await loop.run_in_executor(_executor, _do_sanity)
    caps = results["capabilities"]

    # Persist sanity to config DB
    cid = config_id or current_config_id
    if cid:
        config_db.save_sanity(
            config_id=cid,
            os_sysinfo=results["os"].get("sysinfo", {}),
            idrac_sysinfo=results["idrac"].get("sysinfo", {}),
            idrac_power=results["idrac"].get("thmtest_sample", {}),
            capabilities=caps)

    # Store in per-run telemetry DB too
    if telemetry.DB_PATH:
        if "sysinfo" in results["os"]:
            telemetry.store_system_info("os", results["os"]["sysinfo"])
        if "sysinfo" in results.get("idrac", {}):
            telemetry.store_system_info("idrac", results["idrac"]["sysinfo"])

    return results

# ─── Test execution ──────────────────────────────────────────────────────────

@app.post("/api/test/start")
async def start_test(config: TestConfig):
    """Start a test run with the given configuration."""
    global orchestrator, inbound_collector, outbound_collector
    global current_run_id, current_run_dir

    if not ssh.os_client:
        raise HTTPException(400, "OS not connected")

    if orchestrator and orchestrator.running:
        raise HTTPException(400, "Test already running")

    # Create run
    current_run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    current_run_dir = telemetry.init_db(str(DATA_DIR), current_run_id)

    # Collect system info
    os_info = {}
    idrac_info = {}
    try:
        os_info = ssh.get_os_sysinfo()
        telemetry.store_system_info("os", os_info)
    except:
        pass
    if ssh.idrac_channel:
        try:
            idrac_info = ssh.get_idrac_sysinfo()
            telemetry.store_system_info("idrac", idrac_info)
        except:
            pass

    # Deploy agent
    orchestrator = BenchmarkOrchestrator(ssh, os_pass=stored_os_pass)
    orchestrator.log_callback = _broadcast_log
    orchestrator.deploy_agent()

    # Get server info
    try:
        out, _, _ = ssh.os_exec("nproc", timeout=5)
        total_cores = int(out.strip())
    except:
        total_cores = 4

    try:
        # Find all mounted /mnt/nvme* dirs with at least 1GB free (excludes tiny
        # partitions like nvme0n1p1=1G, nvme1n1p1=94M that fill up during FIO).
        # The OS drive (nvme4n1) has /boot and LVM, not a /mnt mount, so it's
        # automatically excluded by only looking at /mnt/nvme* mountpoints.
        out, _, _ = ssh.os_exec(
            "df -BG /mnt/nvme* 2>/dev/null | awk 'NR>1 && $4+0>=2 {print $6}' | sort | tr '\\n' ' '",
            timeout=5)
        fio_targets = out.strip() or "/tmp"
    except:
        fio_targets = "/tmp"

    phases = config.phases
    if not phases:
        phases = _default_phases(config.phase_duration)

    run_config = {
        "phase_duration": config.phase_duration,
        "rest_duration": config.rest_duration,
        "total_cores": total_cores,
        "fio_targets": fio_targets,
        "phases": phases,
    }

    # Persist run to config DB
    config_db.create_run(
        run_id=current_run_id,
        config_id=config.config_id or current_config_id,
        phase_duration=config.phase_duration,
        rest_duration=config.rest_duration,
        phases=phases,
        total_cores=total_cores,
        fio_targets=fio_targets,
        os_sysinfo=os_info,
        idrac_sysinfo=idrac_info)

    # Phase update callback for DB persistence
    _orig_phase_setter = orchestrator.__class__.current_phase.fget if hasattr(orchestrator.__class__.current_phase, 'fget') else None

    def on_phase_change(phase):
        config_db.update_run_phase(current_run_id, phase)

    orchestrator._phase_change_callback = on_phase_change

    # Start telemetry collectors
    def get_phase():
        return orchestrator.current_phase if orchestrator else ""

    inbound_collector = telemetry.InboundCollector(ssh, interval=2.0, phase_callback=get_phase)
    inbound_collector.start()

    if ssh.idrac_channel:
        outbound_collector = telemetry.OutboundCollector(ssh, interval=5.0, phase_callback=get_phase)
        outbound_collector.start()

    # Start benchmark sequence with completion callback
    def on_complete():
        try:
            summary = generate_summary(telemetry.DB_PATH) if telemetry.DB_PATH else {}
            config_db.finish_run(current_run_id, "completed", summary)
        except:
            config_db.finish_run(current_run_id, "completed")

    orchestrator._completion_callback = on_complete
    orchestrator.run_test_sequence(run_config)

    # Start WS broadcaster
    asyncio.get_event_loop().create_task(_ws_telemetry_loop())

    return {
        "status": "started",
        "run_id": current_run_id,
        "config": run_config,
    }

@app.post("/api/test/stop")
async def stop_test():
    if orchestrator:
        orchestrator.stop()
    _stop_collectors()
    if current_run_id:
        config_db.finish_run(current_run_id, "stopped")
    return {"status": "stopped"}

@app.get("/api/test/status")
async def test_status():
    return {
        "running": orchestrator.running if orchestrator else False,
        "current_phase": orchestrator.current_phase if orchestrator else "none",
        "run_id": current_run_id,
        "log_lines": len(orchestrator.log_lines) if orchestrator else 0,
        "os_connected": ssh.os_client is not None,
        "idrac_connected": ssh.idrac_channel is not None,
    }

@app.get("/api/test/logs")
async def test_logs(offset: int = 0, limit: int = 200):
    if not orchestrator:
        return {"lines": [], "total": 0}
    lines = orchestrator.log_lines[offset:offset + limit]
    return {"lines": lines, "total": len(orchestrator.log_lines), "offset": offset}

# ─── Telemetry endpoints ─────────────────────────────────────────────────────

@app.get("/api/telemetry/os")
async def get_os_telemetry(limit: int = 300):
    return {"data": telemetry.get_os_metrics(limit)}

@app.get("/api/telemetry/power")
async def get_power_telemetry(limit: int = 300):
    return {"data": telemetry.get_power_metrics(limit)}

@app.get("/api/telemetry/latest")
async def get_latest_telemetry():
    os_latest = inbound_collector.latest if inbound_collector else {}
    pwr_latest = outbound_collector.latest if outbound_collector else {}
    return {"os": os_latest, "power": pwr_latest}

@app.get("/api/telemetry/events")
async def get_events():
    return {"data": telemetry.get_benchmark_events()}

@app.get("/api/telemetry/sysinfo")
async def get_sysinfo():
    return {"data": telemetry.get_system_info()}

# ─── Reports ─────────────────────────────────────────────────────────────────

@app.post("/api/report/generate")
async def generate_report():
    if not telemetry.DB_PATH:
        raise HTTPException(400, "No test data available")

    excel_path = str(current_run_dir / f"report_{current_run_id}.xlsx")
    generate_excel_report(telemetry.DB_PATH, excel_path,
                          {"run_id": current_run_id})

    telemetry.export_os_csv(str(current_run_dir / "os_metrics.csv"))
    telemetry.export_power_csv(str(current_run_dir / "power_metrics.csv"))

    summary = generate_summary(telemetry.DB_PATH)

    # Persist summary
    if current_run_id:
        config_db.finish_run(current_run_id, "completed", summary)

    return {
        "status": "generated",
        "excel_path": excel_path,
        "run_id": current_run_id,
        "summary": summary,
    }

@app.get("/api/report/download/{run_id}")
async def download_report(run_id: str):
    report_path = DATA_DIR / run_id / f"report_{run_id}.xlsx"
    if not report_path.exists():
        raise HTTPException(404, "Report not found")
    return FileResponse(str(report_path),
                        filename=f"perf_report_{run_id}.xlsx",
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@app.get("/api/report/summary")
async def get_summary():
    if not telemetry.DB_PATH:
        raise HTTPException(400, "No test data")
    return generate_summary(telemetry.DB_PATH)

# ─── Run history ─────────────────────────────────────────────────────────────

@app.get("/api/runs")
async def list_runs():
    """List all test runs from config DB + file-based fallback."""
    db_runs = config_db.list_runs()
    # Also check file system for any runs not in DB
    known_ids = {r["run_id"] for r in db_runs}
    if DATA_DIR.exists():
        for d in sorted(DATA_DIR.iterdir(), reverse=True):
            if d.is_dir() and (d / "telemetry.db").exists() and d.name not in known_ids:
                db_runs.append({
                    "run_id": d.name,
                    "config_id": None,
                    "config_name": None,
                    "started_at": d.name[:8],
                    "status": "completed",
                    "phases": [],
                })
    # Enrich with file info
    for r in db_runs:
        rid = r["run_id"]
        rd = DATA_DIR / rid
        r["has_report"] = (rd / f"report_{rid}.xlsx").exists()
        r["has_os_csv"] = (rd / "os_metrics.csv").exists()
        r["has_data"] = (rd / "telemetry.db").exists()
    return {"runs": db_runs}

@app.get("/api/runs/{run_id}")
async def get_run(run_id: str):
    """Get detailed info for a single run."""
    run = config_db.get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    rd = DATA_DIR / run_id
    run["has_report"] = (rd / f"report_{run_id}.xlsx").exists()
    run["has_data"] = (rd / "telemetry.db").exists()
    return run

# ─── WebSocket ───────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    ws_clients.append(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        if ws in ws_clients:
            ws_clients.remove(ws)

async def _ws_telemetry_loop():
    """Broadcast telemetry to all WS clients every 2s while test runs."""
    while orchestrator and orchestrator.running:
        if ws_clients:
            msg = {
                "type": "telemetry",
                "os": inbound_collector.latest if inbound_collector else {},
                "power": outbound_collector.latest if outbound_collector else {},
                "phase": orchestrator.current_phase if orchestrator else "",
                "running": orchestrator.running if orchestrator else False,
            }
            dead = []
            for ws in ws_clients:
                try:
                    await ws.send_json(msg)
                except:
                    dead.append(ws)
            for ws in dead:
                if ws in ws_clients:
                    ws_clients.remove(ws)
        await asyncio.sleep(2)
    # Send final "stopped" message
    if ws_clients:
        for ws in ws_clients:
            try:
                await ws.send_json({"type": "test_complete", "run_id": current_run_id})
            except:
                pass

def _broadcast_log(line: str):
    """Broadcast a log line to WS clients (thread-safe)."""
    for ws in list(ws_clients):
        try:
            asyncio.get_event_loop().call_soon_threadsafe(
                asyncio.ensure_future,
                ws.send_json({"type": "log", "line": line})
            )
        except:
            pass

# ─── Helpers ─────────────────────────────────────────────────────────────────

def _stop_collectors():
    global inbound_collector, outbound_collector
    if inbound_collector:
        inbound_collector.stop()
        inbound_collector = None
    if outbound_collector:
        outbound_collector.stop()
        outbound_collector = None

def _default_phases(duration: int) -> list:
    """Default 8-phase test: HPL + FIO only (no stress-ng for portability)."""
    return [
        {"name": "01_idle_baseline", "type": "idle", "duration": max(duration // 3, 10)},
        {"name": "02_hpl_100pct", "type": "hpl_100", "duration": duration},
        {"name": "03_hpl_50pct", "type": "hpl_50", "duration": duration},
        {"name": "04_fio_100pct", "type": "fio_100", "duration": duration},
        {"name": "05_fio_50pct", "type": "fio_50", "duration": duration},
        {"name": "06_hpl_fio_100pct", "type": "hpl_fio_100", "duration": duration},
        {"name": "07_hpl_fio_50pct", "type": "hpl_fio_50", "duration": duration},
        {"name": "08_idle_cooldown", "type": "idle", "duration": max(duration // 3, 10)},
    ]

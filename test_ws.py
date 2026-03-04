"""Test WebSocket connection to the platform server."""
import asyncio
import json
import websockets

async def test_ws():
    uri = "ws://localhost:8001/ws"
    try:
        async with websockets.connect(uri, close_timeout=3) as ws:
            print("WebSocket connected OK")
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=5)
                d = json.loads(msg)
                mtype = d.get("type", "unknown")
                print("Message type:", mtype)
                if mtype == "telemetry":
                    print("  OS keys:", sorted(d.get("os", {}).keys())[:5])
                    print("  Power keys present:", bool(d.get("power")))
                elif mtype == "log":
                    line = d.get("line", "")
                    print("  Log:", line[:80])
            except asyncio.TimeoutError:
                print("No message within 5s (expected if no test running)")
    except Exception as e:
        print("WS Error:", e)

asyncio.run(test_ws())

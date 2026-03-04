"""
Entry point — run the Performance Test Platform server.
Usage: python run.py [--port 8000] [--host 0.0.0.0]
"""

import argparse
import uvicorn

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Performance Test Platform")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    args = parser.parse_args()

    uvicorn.run("backend.app:app", host=args.host, port=args.port, reload=False)

#!/usr/bin/env python3
"""Health check script for Performance Test Platform"""
import sys
import sqlite3
import subprocess
from pathlib import Path

def check_service():
    """Check if the main service is running"""
    try:
        result = subprocess.run(['pgrep', '-f', 'python run.py'], 
                              capture_output=True, text=True)
        return result.returncode == 0
    except:
        return False

def check_database():
    """Check if platform database is accessible"""
    try:
        db_path = Path('/opt/perf-platform/data/platform.db')
        if not db_path.exists():
            return False
        conn = sqlite3.connect(str(db_path))
        conn.execute("SELECT 1 FROM sqlite_master LIMIT 1")
        conn.close()
        return True
    except:
        return False

def check_port():
    """Check if the service port is listening"""
    try:
        result = subprocess.run(['netstat', '-ln'], 
                              capture_output=True, text=True)
        return ':8001' in result.stdout
    except:
        return False

def check_dependencies():
    """Check if required dependencies are available"""
    try:
        # Check Python modules
        import fastapi
        import uvicorn
        import paramiko
        import websockets
        import openpyxl
        return True
    except ImportError as e:
        print(f"Missing dependency: {e}")
        return False

def check_data_directory():
    """Check if data directory is accessible"""
    try:
        data_dir = Path('/opt/perf-platform/data')
        return data_dir.exists() and data_dir.is_dir()
    except:
        return False

def check_recent_runs():
    """Check if there are recent test runs"""
    try:
        data_dir = Path('/opt/perf-platform/data')
        if not data_dir.exists():
            return False
        
        # Look for run directories (timestamp format)
        run_dirs = [d for d in data_dir.iterdir() 
                   if d.is_dir() and d.name.isdigit() and len(d.name) == 15]
        
        if not run_dirs:
            return True  # No runs yet is OK
        
        # Check if any run has data
        for run_dir in sorted(run_dirs, reverse=True)[:5]:  # Check last 5 runs
            db_path = run_dir / 'telemetry.db'
            if db_path.exists():
                conn = sqlite3.connect(str(db_path))
                count = conn.execute("SELECT COUNT(*) FROM os_metrics").fetchone()[0]
                conn.close()
                if count > 0:
                    return True
        
        return False
    except:
        return False

def main():
    """Main health check function"""
    checks = {
        'service': check_service(),
        'database': check_database(),
        'port': check_port(),
        'dependencies': check_dependencies(),
        'data_directory': check_data_directory(),
        'recent_runs': check_recent_runs()
    }
    
    all_passed = all(checks.values())
    
    if all_passed:
        print("HEALTHY")
        print("All health checks passed")
        sys.exit(0)
    else:
        print("UNHEALTHY")
        failed_checks = [name for name, status in checks.items() if not status]
        for name in failed_checks:
            print(f"  {name}: FAILED")
        sys.exit(1)

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""CLI tool for Performance Test Platform"""
import argparse
import json
import sys
import requests
from pathlib import Path
import time

class PerfPlatformCLI:
    def __init__(self, server_url="http://localhost:8001"):
        self.server_url = server_url
        self.session = requests.Session()
        self.session.timeout = 30

    def _request(self, method, endpoint, data=None, json_data=None):
        """Make HTTP request with error handling"""
        url = f"{self.server_url}{endpoint}"
        
        try:
            if method == 'GET':
                response = self.session.get(url)
            elif method == 'POST':
                if json_data:
                    response = self.session.post(url, json=json_data)
                else:
                    response = self.session.post(url, data=data)
            elif method == 'DELETE':
                response = self.session.delete(url)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"Error: {e}")
            sys.exit(1)

    def connect(self, config_file):
        """Connect to server using configuration file"""
        try:
            with open(config_file) as f:
                config = json.load(f)
            
            result = self._request('POST', '/api/connect', json_data=config)
            print(f"Connected: {result}")
            return result
            
        except FileNotFoundError:
            print(f"Error: Configuration file not found: {config_file}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in config file: {e}")
            sys.exit(1)

    def run_test(self, config_file=None, phase_duration=30, rest_duration=10, quick=False):
        """Run a test via API"""
        
        # Load configuration
        config = {}
        if config_file and Path(config_file).exists():
            with open(config_file) as f:
                config = json.load(f)
        
        # Default configuration
        if quick:
            phase_duration = 15
            rest_duration = 5
        
        default_config = {
            "phase_duration": phase_duration,
            "rest_duration": rest_duration,
            "phases": [
                {"name": "01_idle_baseline", "type": "idle", "duration": max(phase_duration // 3, 10)},
                {"name": "02_hpl_100pct", "type": "hpl_100", "duration": phase_duration},
                {"name": "03_hpl_50pct", "type": "hpl_50", "duration": phase_duration},
                {"name": "04_fio_100pct", "type": "fio_100", "duration": phase_duration},
                {"name": "05_fio_50pct", "type": "fio_50", "duration": phase_duration},
                {"name": "06_hpl_fio_100pct", "type": "hpl_fio_100", "duration": phase_duration},
                {"name": "07_hpl_fio_50pct", "type": "hpl_fio_50", "duration": phase_duration},
                {"name": "08_idle_cooldown", "type": "idle", "duration": max(phase_duration // 3, 10)}
            ]
        }
        
        # Merge with provided config
        test_config = {**default_config, **config}
        
        print(f"Starting test with {len(test_config['phases'])} phases...")
        print(f"Phase duration: {test_config['phase_duration']}s")
        print(f"Rest duration: {test_config['rest_duration']}s")
        
        # Start test
        result = self._request('POST', '/api/test/start', json_data=test_config)
        
        run_id = result.get('run_id')
        print(f"✓ Test started successfully!")
        print(f"Run ID: {run_id}")
        print(f"Status: {result.get('status')}")
        
        return run_id

    def get_status(self):
        """Get current test status"""
        try:
            status = self._request('GET', '/api/test/status')
            
            print(f"Running: {status.get('running')}")
            print(f"Phase: {status.get('current_phase')}")
            print(f"Run ID: {status.get('run_id')}")
            print(f"Log lines: {status.get('log_lines')}")
            print(f"OS connected: {status.get('os_connected')}")
            print(f"iDRAC connected: {status.get('idrac_connected')}")
            
            return status
            
        except Exception as e:
            print(f"Error getting status: {e}")
            return None

    def stop_test(self):
        """Stop current test"""
        try:
            result = self._request('POST', '/api/test/stop')
            print(f"✓ Test stopped: {result.get('status')}")
            return result
            
        except Exception as e:
            print(f"Error stopping test: {e}")
            return None

    def generate_report(self):
        """Generate test report"""
        try:
            result = self._request('POST', '/api/report/generate')
            print(f"✓ Report generated: {result.get('status')}")
            print(f"Run ID: {result.get('run_id')}")
            print(f"Excel path: {result.get('excel_path')}")
            
            return result
            
        except Exception as e:
            print(f"Error generating report: {e}")
            return None

    def monitor_test(self, run_id=None, interval=10):
        """Monitor test progress in real-time"""
        print(f"Monitoring test (Ctrl+C to stop)...")
        
        try:
            while True:
                status = self.get_status()
                if not status or not status.get('running'):
                    print("Test completed or stopped")
                    break
                
                print(f"[{time.strftime('%H:%M:%S')}] Phase: {status.get('current_phase')} | "
                      f"Running: {status.get('running')} | "
                      f"Log lines: {status.get('log_lines')}")
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\nMonitoring stopped by user")

    def get_logs(self, limit=50, offset=0):
        """Get recent log lines"""
        try:
            result = self._request('GET', f'/api/test/logs?limit={limit}&offset={offset}')
            lines = result.get('lines', [])
            
            for line in lines:
                print(line)
                
            return result
            
        except Exception as e:
            print(f"Error getting logs: {e}")
            return None

    def list_runs(self):
        """List all test runs"""
        try:
            result = self._request('GET', '/api/runs')
            runs = result.get('runs', [])
            
            if not runs:
                print("No test runs found")
                return
            
            print(f"{'Run ID':<20} {'Status':<12} {'Started':<20} {'Duration':<10}")
            print("-" * 70)
            
            for run in runs:
                duration = "N/A"
                if run.get('started_at') and run.get('finished_at'):
                    try:
                        start = run['started_at'].replace('T', ' ').replace('Z', '')
                        end = run['finished_at'].replace('T', ' ').replace('Z', '')
                        duration = f"{end - start}"
                    except:
                        pass
                
                print(f"{run['run_id']:<20} {run['status']:<12} {run['started_at']:<20} {duration:<10}")
                
            return result
            
        except Exception as e:
            print(f"Error listing runs: {e}")
            return None

    def download_report(self, run_id, output_path=None):
        """Download Excel report for a specific run"""
        try:
            response = self.session.get(f"{self.server_url}/api/report/download/{run_id}")
            response.raise_for_status()
            
            if not output_path:
                output_path = f"report_{run_id}.xlsx"
            
            with open(output_path, 'wb') as f:
                f.write(response.content)
            
            print(f"✓ Report downloaded: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"Error downloading report: {e}")
            return None

    def health_check(self):
        """Perform health check"""
        try:
            status = self.get_status()
            if status:
                print("✓ Platform is healthy")
                return True
            else:
                print("✗ Platform is not responding")
                return False
                
        except Exception as e:
            print(f"✗ Health check failed: {e}")
            return False

def main():
    parser = argparse.ArgumentParser(description='Performance Test Platform CLI')
    parser.add_argument('--server', default='http://localhost:8001', 
                       help='Platform server URL')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Connect command
    connect_parser = subparsers.add_parser('connect', help='Connect to server')
    connect_parser.add_argument('config', help='Configuration file (JSON)')
    
    # Run command
    run_parser = subparsers.add_parser('run', help='Run a test')
    run_parser.add_argument('--config', help='Configuration file (JSON)')
    run_parser.add_argument('--phase-duration', type=int, default=30,
                          help='Phase duration in seconds')
    run_parser.add_argument('--rest-duration', type=int, default=10,
                          help='Rest duration in seconds')
    run_parser.add_argument('--quick', action='store_true',
                          help='Run quick test (15s phases)')
    run_parser.add_argument('--monitor', action='store_true',
                          help='Monitor test progress in real-time')
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Get test status')
    
    # Stop command
    subparsers.add_parser('stop', help='Stop current test')
    
    # Report command
    report_parser = subparsers.add_parser('report', help='Generate report')
    report_parser.add_argument('--download', action='store_true',
                             help='Download generated report')
    
    # Logs command
    logs_parser = subparsers.add_parser('logs', help='Get test logs')
    logs_parser.add_argument('--limit', type=int, default=50,
                           help='Number of log lines to show')
    logs_parser.add_argument('--offset', type=int, default=0,
                           help='Log line offset')
    
    # Runs command
    runs_parser = subparsers.add_parser('runs', help='List test runs')
    
    # Health command
    subparsers.add_parser('health', help='Perform health check')
    
    args = parser.parse_args()
    
    cli = PerfPlatformCLI(args.server)
    
    if args.command == 'connect':
        cli.connect(args.config)
    
    elif args.command == 'run':
        run_id = cli.run_test(
            config_file=args.config,
            phase_duration=args.phase_duration,
            rest_duration=args.rest_duration,
            quick=args.quick
        )
        
        if args.monitor:
            cli.monitor_test(run_id)
    
    elif args.command == 'status':
        cli.get_status()
    
    elif args.command == 'stop':
        cli.stop_test()
    
    elif args.command == 'report':
        result = cli.generate_report()
        if args.download and result:
            run_id = result.get('run_id')
            if run_id:
                cli.download_report(run_id)
    
    elif args.command == 'logs':
        cli.get_logs(limit=args.limit, offset=args.offset)
    
    elif args.command == 'runs':
        cli.list_runs()
    
    elif args.command == 'health':
        cli.health_check()
    
    else:
        parser.print_help()

if __name__ == '__main__':
    main()

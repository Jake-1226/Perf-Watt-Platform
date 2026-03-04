#!/bin/bash
# Automated end-to-end test script for Performance Test Platform

set -euo pipefail

# Configuration
PLATFORM_URL="${PLATFORM_URL:-http://localhost:8001}"
CONFIG_FILE="${CONFIG_FILE:-}"
PHASE_DURATION="${PHASE_DURATION:-30}"
REST_DURATION="${REST_DURATION:-10}"
QUICK_TEST="${QUICK_TEST:-false}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check if platform is running
    if ! curl -s "$PLATFORM_URL/api/configs" >/dev/null 2>&1; then
        error "Platform is not running at $PLATFORM_URL"
    fi
    
    # Check CLI tool
    if ! command -v /opt/perf-platform/cli.py >/dev/null 2>&1; then
        error "CLI tool not found at /opt/perf-platform/cli.py"
    fi
    
    # Check health
    if ! /opt/perf-platform/health_check.py >/dev/null 2>&1; then
        warn "Health check failed, but continuing..."
    fi
    
    log "Prerequisites check passed"
}

connect_to_server() {
    if [[ -n "$CONFIG_FILE" ]]; then
        log "Connecting to server using config: $CONFIG_FILE"
        
        if [[ ! -f "$CONFIG_FILE" ]]; then
            error "Configuration file not found: $CONFIG_FILE"
        fi
        
        # Validate JSON config
        if ! python3 -c "import json; json.load(open('$CONFIG_FILE'))" 2>/dev/null; then
            error "Invalid JSON in configuration file: $CONFIG_FILE"
        fi
        
        # Connect
        result=$(curl -s -X POST "$PLATFORM_URL/api/connect" \
                     -H "Content-Type: application/json" \
                     -d @"$CONFIG_FILE")
        
        if [[ $? -eq 0 ]]; then
            log "✓ Connected to server successfully"
        else
            error "Failed to connect to server"
        fi
    else
        log "No configuration file provided, skipping connection"
    fi
}

run_sanity_check() {
    log "Running sanity check..."
    
    result=$(curl -s -X POST "$PLATFORM_URL/api/sanity_check")
    
    if [[ $? -eq 0 ]]; then
        log "✓ Sanity check completed"
        
        # Extract and display key info
        os_status=$(echo "$result" | python3 -c "
import sys, json
data = json.load(sys.stdin)
if data.get('os', {}).get('sysinfo', {}).get('hostname'):
    print(f\"OS Hostname: {data['os']['sysinfo']['hostname']}\")
if data.get('os', {}).get('capabilities', {}).get('stress-ng'):
    print(f\"stress-ng: {'Available' if data['os']['capabilities']['stress-ng'] else 'Missing'}\")
if data.get('os', {}).get('capabilities', {}).get('fio'):
    print(f\"FIO: {'Available' if data['os']['capabilities']['fio'] else 'Missing'}\")
")
        
        if [[ -n "$os_status" ]]; then
            echo "$os_status"
        fi
    else
        warn "Sanity check completed with warnings"
    fi
}

start_test() {
    log "Starting automated test..."
    
    # Prepare CLI command
    cli_cmd="/opt/perf-platform/cli.py --server $PLATFORM_URL run"
    
    if [[ "$QUICK_TEST" == "true" ]]; then
        cli_cmd="$cli_cmd --quick"
        log "Running quick test (15s phases)"
    else
        cli_cmd="$cli_cmd --phase-duration $PHASE_DURATION --rest-duration $REST_DURATION"
        log "Running full test (${PHASE_DURATION}s phases, ${REST_DURATION}s rest)"
    fi
    
    if [[ -n "$CONFIG_FILE" ]]; then
        cli_cmd="$cli_cmd --config $CONFIG_FILE"
    fi
    
    # Start test and capture run ID
    log "Executing: $cli_cmd"
    TEST_OUTPUT=$($cli_cmd 2>&1)
    
    # Extract run ID
    RUN_ID=$(echo "$TEST_OUTPUT" | grep "Run ID:" | cut -d' ' -f3)
    
    if [[ -n "$RUN_ID" ]]; then
        log "✓ Test started successfully"
        log "Run ID: $RUN_ID"
        echo "$RUN_ID" > /tmp/test_run_id
    else
        error "Failed to start test"
    fi
}

monitor_test() {
    local run_id="$1"
    local max_wait_time="${2:-3600}"  # Default 1 hour max wait
    local start_time=$(date +%s)
    
    log "Monitoring test progress (Run ID: $run_id)..."
    
    while true; do
        current_time=$(date +%s)
        elapsed=$((current_time - start_time))
        
        if [[ $elapsed -gt $max_wait_time ]]; then
            warn "Test monitoring timeout after ${max_wait_time}s"
            break
        fi
        
        # Get status
        status=$(curl -s "$PLATFORM_URL/api/test/status")
        
        if [[ $? -ne 0 ]]; then
            warn "Failed to get test status"
            sleep 10
            continue
        fi
        
        # Parse status
        running=$(echo "$status" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(data.get('running', False))
")
        
        phase=$(echo "$status" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(data.get('current_phase', 'unknown'))
")
        
        log_lines=$(echo "$status" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(data.get('log_lines', 0))
")
        
        # Display progress
        echo "[$(date '+%H:%M:%S')] Phase: $phase | Running: $running | Logs: $log_lines"
        
        # Check if test completed
        if [[ "$running" == "False" ]]; then
            log "✓ Test completed"
            break
        fi
        
        sleep 10
    done
}

generate_report() {
    local run_id="$1"
    
    log "Generating report for Run ID: $run_id"
    
    result=$(curl -s -X POST "$PLATFORM_URL/api/report/generate")
    
    if [[ $? -eq 0 ]]; then
        log "✓ Report generated successfully"
        
        # Extract report info
        echo "$result" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"Status: {data.get('status')}\")
print(f\"Run ID: {data.get('run_id')}\")
if data.get('excel_path'):
    print(f\"Excel: {data['excel_path']}\")
"
    else
        warn "Report generation completed with warnings"
    fi
}

download_report() {
    local run_id="$1"
    local output_dir="${2:-/tmp}"
    
    log "Downloading report for Run ID: $run_id"
    
    output_path="$output_dir/report_${run_id}.xlsx"
    
    if curl -s "$PLATFORM_URL/api/report/download/$run_id" -o "$output_path"; then
        log "✓ Report downloaded: $output_path"
        
        # Check file size
        if [[ -f "$output_path" ]]; then
            size=$(stat -f "$output_path" | cut -d' ' -f5)
            log "Report file size: $(numfmt --to=iec $size)"
        fi
    else
        error "Failed to download report"
    fi
}

cleanup() {
    log "Performing cleanup..."
    
    # Stop any running test
    curl -s -X POST "$PLATFORM_URL/api/test/stop" >/dev/null 2>&1
    
    # Clean up temporary files
    rm -f /tmp/test_run_id
    
    log "Cleanup completed"
}

main() {
    log "Starting automated end-to-end test..."
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --quick)
                QUICK_TEST=true
                PHASE_DURATION=15
                REST_DURATION=5
                shift
                ;;
            --config)
                CONFIG_FILE="$2"
                shift 2
                ;;
            --platform-url)
                PLATFORM_URL="$2"
                shift 2
                ;;
            --phase-duration)
                PHASE_DURATION="$2"
                shift 2
                ;;
            --rest-duration)
                REST_DURATION="$2"
                shift 2
                ;;
            --download-reports)
                DOWNLOAD_REPORTS_DIR="$2"
                shift 2
                ;;
            --help|-h)
                echo "Usage: $0 [options]"
                echo "Options:"
                echo "  --quick                    Run quick test (15s phases)"
                echo "  --config FILE             Use configuration file"
                echo "  --platform-url URL        Platform server URL"
                echo "  --phase-duration SECONDS  Phase duration in seconds"
                echo "  --rest-duration SECONDS   Rest duration in seconds"
                echo "  --download-reports DIR     Download reports to directory"
                echo "  --help, -h                Show this help"
                exit 0
                ;;
            *)
                error "Unknown option: $1"
                ;;
        esac
    done
    
    # Execute test sequence
    check_prerequisites
    connect_to_server
    run_sanity_check
    start_test
    
    # Get run ID
    RUN_ID=$(cat /tmp/test_run_id 2>/dev/null || echo "")
    
    if [[ -n "$RUN_ID" ]]; then
        monitor_test "$RUN_ID"
        generate_report "$RUN_ID"
        
        if [[ -n "${DOWNLOAD_REPORTS_DIR:-}" ]]; then
            download_report "$RUN_ID" "$DOWNLOAD_REPORTS_DIR"
        fi
    else
        error "No test run ID available"
    fi
    
    cleanup
    
    log "Automated test completed successfully!"
    echo ""
    echo "Test Results Summary:"
    echo "  Platform URL: $PLATFORM_URL"
    if [[ -n "$RUN_ID" ]]; then
        echo "  Run ID: $RUN_ID"
        if [[ -n "${DOWNLOAD_REPORTS_DIR:-}" ]]; then
            echo "  Reports: $DOWNLOAD_REPORTS_DIR"
        fi
    fi
    echo "  Timestamp: $(date)"
}

# Error handling
trap cleanup EXIT

# Run main function
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi

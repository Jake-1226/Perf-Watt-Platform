#!/bin/bash
# Example scheduler script for Performance Test Platform
# Can be used with cron or other scheduling systems

# Add to crontab for scheduled runs:
# 0 2 * * * /opt/perf-platform/scripts/scheduler_example.sh
# 0 14 * * * /opt/perf-platform/scripts/scheduler_example.sh --quick

set -euo pipefail

# Configuration
PLATFORM_URL="${PLATFORM_URL:-http://localhost:8001}"
CONFIG_FILE="${CONFIG_FILE:-/opt/perf-platform/configs/production.json}"
LOG_DIR="${LOG_DIR:-/opt/perf-platform/logs}"
QUICK_TEST="${QUICK_TEST:-false}"

# Create log directory
mkdir -p "$LOG_DIR"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_DIR/scheduler_$(date +%Y%m%d).log"
}

error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1" | tee -a "$LOG_DIR/scheduler_$(date +%Y%m%d).log"
    exit 1
}

# Check if platform is healthy
check_platform_health() {
    if ! /opt/perf-platform/health_check.py >/dev/null 2>&1; then
        error "Platform health check failed"
    fi
    
    if ! curl -s "$PLATFORM_URL/api/configs" >/dev/null 2>&1; then
        error "Platform API not responding"
    fi
}

# Run automated test
run_automated_test() {
    local test_type="$1"
    
    log "Starting scheduled test: $test_type"
    
    # Prepare test command
    test_cmd="/opt/perf-platform/scripts/run_automated_test.sh"
    
    if [[ "$QUICK_TEST" == "true" ]]; then
        test_cmd="$test_cmd --quick"
    fi
    
    if [[ -n "$CONFIG_FILE" ]]; then
        test_cmd="$test_cmd --config $CONFIG_FILE"
    fi
    
    if [[ -n "$PLATFORM_URL" ]]; then
        test_cmd="$test_cmd --platform-url $PLATFORM_URL"
    fi
    
    log "Executing: $test_cmd"
    
    # Run the test and capture output
    if ! $test_cmd >> "$LOG_DIR/scheduler_$(date +%Y%m%d).log" 2>&1; then
        error "Automated test failed"
    fi
    
    log "Scheduled test completed successfully"
}

# Send notification (optional)
send_notification() {
    local message="$1"
    local webhook_url="${WEBHOOK_URL:-}"
    
    if [[ -n "$webhook_url" ]]; then
        curl -X POST "$webhook_url" \
             -H "Content-Type: application/json" \
             -d "{\"text\": \"Performance Test Platform\", \"message\": \"$message\"}" \
             >/dev/null 2>&1 || true
    fi
    
    # You can add other notification methods here:
    # - Email
    # - Slack
    # - Microsoft Teams
    # - Discord
}

main() {
    local test_type="${1:-full}"
    
    log "Starting scheduled test: $test_type"
    
    # Check platform health
    check_platform_health
    
    # Run the test
    run_automated_test "$test_type"
    
    # Send notification
    send_notification "Scheduled test '$test_type' completed successfully"
    
    log "Scheduled test completed"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --quick)
            QUICK_TEST=true
            test_type="quick"
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
        --log-dir)
            LOG_DIR="$2"
            shift 2
            ;;
        --webhook)
            WEBHOOK_URL="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [options] [test_type]"
            echo "Options:"
            echo "  --quick                    Run quick test (15s phases)"
            echo "  --config FILE             Use configuration file"
            echo "  --platform-url URL        Platform server URL"
            echo "  --log-dir DIR             Log directory"
            echo "  --webhook URL             Webhook URL for notifications"
            echo "  --help, -h                Show this help"
            echo ""
            echo "Test types:"
            echo "  full                      Full test (default)"
            echo "  quick                     Quick test"
            exit 0
            ;;
        -*)
            error "Unknown option: $1"
            ;;
        *)
            test_type="$1"
            shift
            ;;
    esac
done

# Run main function
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "${test_type:-full}"
fi

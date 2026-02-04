#!/bin/bash

# Nestle API Manager - Start, Stop, Restart, Status
# Usage: ./start_api.sh [start|stop|restart|status]
# Default action: start

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PID_FILE="$PROJECT_ROOT/.api.pid"
LOG_FILE="$PROJECT_ROOT/logs/api.log"
API_HOST="0.0.0.0"
API_PORT="8000"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored message
print_msg() {
    local color=$1
    local msg=$2
    echo -e "${color}${msg}${NC}"
}

# Print header
print_header() {
    echo ""
    echo "=========================================="
    echo "  Nestle API Backend Manager"
    echo "=========================================="
    echo ""
}

# Activate conda environment
activate_conda() {
    eval "$(conda shell.bash hook)"
    conda activate nestle 2>/dev/null || {
        print_msg "$RED" "Error: Failed to activate conda environment 'nestle'"
        print_msg "$YELLOW" "Please create it first: conda create -n nestle python=3.11"
        exit 1
    }
}

# Check if API is running
is_running() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

# Get API status
get_status() {
    if is_running; then
        local pid=$(cat "$PID_FILE")
        print_msg "$GREEN" "● API is RUNNING (PID: $pid)"
        print_msg "$BLUE" "  URL: http://localhost:$API_PORT"
        print_msg "$BLUE" "  Docs: http://localhost:$API_PORT/docs"
        return 0
    else
        print_msg "$RED" "○ API is STOPPED"
        return 1
    fi
}

# Stop the API
stop_api() {
    print_header
    print_msg "$YELLOW" "Stopping API server..."

    if is_running; then
        local pid=$(cat "$PID_FILE")
        kill "$pid" 2>/dev/null || true

        # Wait for process to terminate (max 10 seconds)
        local count=0
        while ps -p "$pid" > /dev/null 2>&1 && [ $count -lt 10 ]; do
            sleep 1
            count=$((count + 1))
        done

        # Force kill if still running
        if ps -p "$pid" > /dev/null 2>&1; then
            print_msg "$YELLOW" "Force killing process..."
            kill -9 "$pid" 2>/dev/null || true
        fi

        rm -f "$PID_FILE"
        print_msg "$GREEN" "✓ API stopped successfully"
    else
        print_msg "$YELLOW" "API was not running"
    fi
}

# Start the API
start_api() {
    print_header
    print_msg "$BLUE" "Starting API server..."

    # Change to project root
    cd "$PROJECT_ROOT"
    print_msg "$BLUE" "Working directory: $PROJECT_ROOT"

    # Activate conda environment
    print_msg "$BLUE" "Activating conda environment: nestle..."
    activate_conda

    # Check if already running
    if is_running; then
        print_msg "$YELLOW" "API is already running!"
        get_status
        exit 1
    fi

    # Check dependencies
    print_msg "$BLUE" "Checking dependencies..."
    python -c "import fastapi" 2>/dev/null || {
        print_msg "$YELLOW" "Installing API dependencies..."
        pip install -r requirements-api.txt -q
    }

    # Check config
    if [ ! -f "config/api_config.yaml" ]; then
        print_msg "$YELLOW" "Warning: config/api_config.yaml not found"
    fi

    # Load environment variables
    if [ -f ".env" ]; then
        print_msg "$BLUE" "Loading environment variables from .env..."
        while IFS='=' read -r key value; do
            if [[ ! "$key" =~ ^# && -n "$key" ]]; then
                value=$(echo "$value" | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")
                export "$key=$value"
            fi
        done < .env
    fi

    # Set PYTHONPATH
    export PYTHONPATH="${PYTHONPATH}:$(pwd)"

    # Create logs directory
    mkdir -p "$(dirname "$LOG_FILE")"

    # Navigate to API directory
    cd src/api

    # Start uvicorn in background
    print_msg "$BLUE" "Starting uvicorn server..."
    nohup uvicorn main:app --reload --host $API_HOST --port $API_PORT > "$LOG_FILE" 2>&1 &
    local pid=$!

    # Save PID
    echo "$pid" > "$PID_FILE"

    # Wait briefly to check if it started successfully
    sleep 2

    if ps -p "$pid" > /dev/null 2>&1; then
        print_msg "$GREEN" "✓ API started successfully!"
        echo ""
        print_msg "$BLUE" "API endpoints:"
        print_msg "$BLUE" "  • Main API:   http://localhost:$API_PORT"
        print_msg "$BLUE" "  • Docs:       http://localhost:$API_PORT/docs"
        print_msg "$BLUE" "  • Redoc:      http://localhost:$API_PORT/redoc"
        print_msg "$BLUE" "  • OpenAPI:    http://localhost:$API_PORT/openapi.json"
        echo ""
        print_msg "$BLUE" "Logs: $LOG_FILE"
        print_msg "$YELLOW" "Press Ctrl+C to stop (if running in foreground)"
        print_msg "$YELLOW" "Or use: $0 stop"
    else
        print_msg "$RED" "✗ Failed to start API. Check logs: $LOG_FILE"
        rm -f "$PID_FILE"
        exit 1
    fi
}

# Restart the API
restart_api() {
    print_header
    print_msg "$YELLOW" "Restarting API server..."
    stop_api
    sleep 1
    start_api
}

# Show usage
show_usage() {
    print_header
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  start    Start the API server (default)"
    echo "  stop     Stop the running API server"
    echo "  restart  Restart the API server"
    echo "  status   Show API server status"
    echo "  logs     Show API logs (tail -f)"
    echo ""
    echo "Examples:"
    echo "  $0           # Start API"
    echo "  $0 start     # Start API"
    echo "  $0 stop      # Stop API"
    echo "  $0 restart   # Restart API"
    echo "  $0 status    # Check status"
    echo "  $0 logs      # Follow logs"
    echo ""
}

# Show logs
show_logs() {
    if [ -f "$LOG_FILE" ]; then
        tail -f "$LOG_FILE"
    else
        print_msg "$RED" "Log file not found: $LOG_FILE"
        exit 1
    fi
}

# Main logic
main() {
    local command="${1:-start}"

    case "$command" in
        start)
            start_api
            ;;
        stop)
            stop_api
            ;;
        restart)
            restart_api
            ;;
        status)
            print_header
            get_status
            ;;
        logs)
            show_logs
            ;;
        help|--help|-h)
            show_usage
            ;;
        *)
            print_msg "$RED" "Unknown command: $command"
            echo ""
            show_usage
            exit 1
            ;;
    esac
}

# Run main
main "$@"

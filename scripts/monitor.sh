#!/bin/bash

# Crypto TGE Monitor Management Script
# This script provides easy management commands for the monitoring system

set -e

# Configuration
APP_NAME="crypto-tge-monitor"
APP_DIR="/opt/$APP_NAME"
SERVICE_USER="crypto-monitor"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
}

info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

# Show usage
show_usage() {
    echo "Crypto TGE Monitor Management Script"
    echo ""
    echo "Usage: $0 <command>"
    echo ""
    echo "Commands:"
    echo "  start       Start the monitoring service"
    echo "  stop        Stop the monitoring service"
    echo "  restart     Restart the monitoring service"
    echo "  status      Show service status"
    echo "  logs        Show service logs (follow mode)"
    echo "  logs-tail   Show last 100 lines of logs"
    echo "  test        Run system test"
    echo "  config      Validate configuration"
    echo "  stats       Show monitoring statistics"
    echo "  health      Show health check results"
    echo "  update      Update the application"
    echo "  backup      Backup application data"
    echo "  restore     Restore application data"
    echo "  help        Show this help message"
}

# Check if service is running
is_running() {
    systemctl is-active --quiet "$APP_NAME"
}

# Start service
start_service() {
    if is_running; then
        warn "Service is already running"
        return 0
    fi
    
    log "Starting $APP_NAME service..."
    systemctl start "$APP_NAME"
    
    if is_running; then
        log "Service started successfully"
    else
        error "Failed to start service"
        return 1
    fi
}

# Stop service
stop_service() {
    if ! is_running; then
        warn "Service is not running"
        return 0
    fi
    
    log "Stopping $APP_NAME service..."
    systemctl stop "$APP_NAME"
    
    if ! is_running; then
        log "Service stopped successfully"
    else
        error "Failed to stop service"
        return 1
    fi
}

# Restart service
restart_service() {
    log "Restarting $APP_NAME service..."
    systemctl restart "$APP_NAME"
    
    if is_running; then
        log "Service restarted successfully"
    else
        error "Failed to restart service"
        return 1
    fi
}

# Show service status
show_status() {
    log "Service Status:"
    systemctl status "$APP_NAME" --no-pager
    
    echo ""
    log "Application Status:"
    sudo -u "$SERVICE_USER" "$APP_DIR/venv/bin/python" "$APP_DIR/src/main.py" --mode status
}

# Show logs
show_logs() {
    log "Showing service logs (Ctrl+C to exit):"
    journalctl -u "$APP_NAME" -f
}

# Show logs tail
show_logs_tail() {
    log "Last 100 lines of service logs:"
    journalctl -u "$APP_NAME" -n 100 --no-pager
}

# Run system test
run_test() {
    log "Running system test..."
    sudo -u "$SERVICE_USER" "$APP_DIR/venv/bin/python" "$APP_DIR/src/main.py" --mode test
}

# Validate configuration
validate_config() {
    log "Validating configuration..."
    sudo -u "$SERVICE_USER" "$APP_DIR/venv/bin/python" -c "
import sys
sys.path.append('$APP_DIR/src')
from config import validate_config
results = validate_config()
for component, status in results.items():
    print(f'{component}: {\"✅ PASS\" if status else \"❌ FAIL\"}')
"
}

# Show statistics
show_stats() {
    log "Monitoring Statistics:"
    sudo -u "$SERVICE_USER" "$APP_DIR/venv/bin/python" "$APP_DIR/src/main.py" --mode status
}

# Show health check
show_health() {
    log "Health Check Results:"
    sudo -u "$SERVICE_USER" "$APP_DIR/venv/bin/python" -c "
import sys
sys.path.append('$APP_DIR/src')
from main import CryptoTGEMonitor
monitor = CryptoTGEMonitor()
health_results = monitor.health_checker.run_checks()
for check, result in health_results.items():
    status = result['status']
    duration = result.get('duration', 0)
    print(f'{check}: {status.upper()} ({duration:.3f}s)')
"
}

# Update application
update_app() {
    log "Updating application..."
    
    # Stop service
    if is_running; then
        stop_service
    fi
    
    # Backup current version
    backup_app
    
    # Update code (assuming git repository)
    cd "$APP_DIR"
    if [ -d ".git" ]; then
        sudo -u "$SERVICE_USER" git pull
    else
        warn "Not a git repository, manual update required"
        return 1
    fi
    
    # Update dependencies
    sudo -u "$SERVICE_USER" "$APP_DIR/venv/bin/pip" install -r requirements.txt
    
    # Start service
    start_service
    
    log "Update completed successfully"
}

# Backup application data
backup_app() {
    BACKUP_DIR="/opt/backups/$APP_NAME"
    BACKUP_FILE="$BACKUP_DIR/backup-$(date +%Y%m%d-%H%M%S).tar.gz"
    
    log "Creating backup..."
    mkdir -p "$BACKUP_DIR"
    
    tar -czf "$BACKUP_FILE" \
        -C "$APP_DIR" \
        logs/ data/ .env \
        --exclude="*.pyc" \
        --exclude="__pycache__"
    
    log "Backup created: $BACKUP_FILE"
}

# Restore application data
restore_app() {
    if [ -z "$1" ]; then
        error "Please specify backup file to restore"
    fi
    
    BACKUP_FILE="$1"
    
    if [ ! -f "$BACKUP_FILE" ]; then
        error "Backup file not found: $BACKUP_FILE"
    fi
    
    log "Restoring from backup: $BACKUP_FILE"
    
    # Stop service
    if is_running; then
        stop_service
    fi
    
    # Extract backup
    tar -xzf "$BACKUP_FILE" -C "$APP_DIR"
    
    # Set ownership
    chown -R "$SERVICE_USER:$SERVICE_USER" "$APP_DIR"
    
    # Start service
    start_service
    
    log "Restore completed successfully"
}

# Main script logic
case "${1:-help}" in
    start)
        start_service
        ;;
    stop)
        stop_service
        ;;
    restart)
        restart_service
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    logs-tail)
        show_logs_tail
        ;;
    test)
        run_test
        ;;
    config)
        validate_config
        ;;
    stats)
        show_stats
        ;;
    health)
        show_health
        ;;
    update)
        update_app
        ;;
    backup)
        backup_app
        ;;
    restore)
        restore_app "$2"
        ;;
    help|--help|-h)
        show_usage
        ;;
    *)
        error "Unknown command: $1"
        show_usage
        exit 1
        ;;
esac

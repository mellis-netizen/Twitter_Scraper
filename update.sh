#!/bin/bash

# Crypto TGE Monitor - Update Script
# This script pulls latest changes and restarts the service

set -e

# Configuration
APP_NAME="crypto-tge-monitor"
APP_DIR="/opt/$APP_NAME"
SERVICE_NAME="crypto-tge-monitor"
REPO_URL="https://github.com/YOUR_USERNAME/YOUR_REPO.git"  # Update this

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    error "This script must be run as root"
fi

log "Starting update process..."

# Stop the service
log "Stopping $SERVICE_NAME service..."
systemctl stop $SERVICE_NAME

# Backup current version
log "Creating backup..."
if [ -d "$APP_DIR/current" ]; then
    mv $APP_DIR/current $APP_DIR/backup-$(date +%Y%m%d_%H%M%S)
fi

# Clone/pull latest code
log "Pulling latest code..."
if [ -d "$APP_DIR/repo" ]; then
    cd $APP_DIR/repo
    git pull origin main
else
    git clone $REPO_URL $APP_DIR/repo
fi

# Copy new code
log "Deploying new code..."
mkdir -p $APP_DIR/current
cp -r $APP_DIR/repo/src/ $APP_DIR/current/
cp $APP_DIR/repo/config.py $APP_DIR/current/
cp $APP_DIR/repo/requirements.txt $APP_DIR/current/
cp $APP_DIR/repo/CLAUDE.md $APP_DIR/current/

# Update dependencies
log "Updating Python dependencies..."
sudo -u $APP_NAME $APP_DIR/venv/bin/pip install -r $APP_DIR/current/requirements.txt

# Set ownership
chown -R $APP_NAME:$APP_NAME $APP_DIR/current

# Start the service
log "Starting $SERVICE_NAME service..."
systemctl start $SERVICE_NAME

# Check status
sleep 5
if systemctl is-active --quiet $SERVICE_NAME; then
    log "Update completed successfully! Service is running."
    systemctl status $SERVICE_NAME --no-pager -l
else
    error "Service failed to start after update. Check logs with: journalctl -u $SERVICE_NAME -n 50"
fi

log "Update process completed!"
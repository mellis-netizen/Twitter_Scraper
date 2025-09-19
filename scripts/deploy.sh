#!/bin/bash

# Crypto TGE Monitor Deployment Script
# This script sets up the monitoring system for production deployment

set -e

# Configuration
APP_NAME="crypto-tge-monitor"
APP_DIR="/opt/$APP_NAME"
SERVICE_USER="crypto-monitor"
VENV_DIR="$APP_DIR/venv"
LOG_DIR="/var/log/$APP_NAME"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
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

log "Starting deployment of $APP_NAME..."

# Create service user
if ! id "$SERVICE_USER" &>/dev/null; then
    log "Creating service user: $SERVICE_USER"
    useradd -r -s /bin/false -d "$APP_DIR" "$SERVICE_USER"
else
    log "Service user $SERVICE_USER already exists"
fi

# Create application directory
log "Creating application directory: $APP_DIR"
mkdir -p "$APP_DIR"
mkdir -p "$LOG_DIR"

# Copy application files
log "Copying application files..."
cp -r . "$APP_DIR/"
cd "$APP_DIR"

# Set ownership
chown -R "$SERVICE_USER:$SERVICE_USER" "$APP_DIR"
chown -R "$SERVICE_USER:$SERVICE_USER" "$LOG_DIR"

# Create virtual environment
log "Creating Python virtual environment..."
sudo -u "$SERVICE_USER" python3 -m venv "$VENV_DIR"

# Install dependencies
log "Installing Python dependencies..."
sudo -u "$SERVICE_USER" "$VENV_DIR/bin/pip" install --upgrade pip
sudo -u "$SERVICE_USER" "$VENV_DIR/bin/pip" install -r requirements.txt

# Create necessary directories
log "Creating necessary directories..."
sudo -u "$SERVICE_USER" mkdir -p "$APP_DIR/logs"
sudo -u "$SERVICE_USER" mkdir -p "$APP_DIR/data"

# Install systemd service
log "Installing systemd service..."
cp systemd/crypto-tge-monitor.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable "$APP_NAME"

# Set up log rotation
log "Setting up log rotation..."
cat > /etc/logrotate.d/$APP_NAME << EOF
$LOG_DIR/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 $SERVICE_USER $SERVICE_USER
    postrotate
        systemctl reload $APP_NAME > /dev/null 2>&1 || true
    endscript
}
EOF

# Create environment file template if it doesn't exist
if [ ! -f "$APP_DIR/.env" ]; then
    log "Creating environment file template..."
    cp env.template "$APP_DIR/.env"
    chown "$SERVICE_USER:$SERVICE_USER" "$APP_DIR/.env"
    warn "Please edit $APP_DIR/.env with your configuration before starting the service"
fi

# Set up firewall rules (if ufw is available)
if command -v ufw &> /dev/null; then
    log "Setting up firewall rules..."
    ufw allow 22/tcp comment "SSH"
    # Add more rules as needed for web interface
fi

# Test the installation
log "Testing installation..."
sudo -u "$SERVICE_USER" "$VENV_DIR/bin/python" src/main.py --mode test

if [ $? -eq 0 ]; then
    log "Installation test passed!"
else
    error "Installation test failed!"
fi

log "Deployment completed successfully!"
log ""
log "Next steps:"
log "1. Edit $APP_DIR/.env with your configuration"
log "2. Start the service: systemctl start $APP_NAME"
log "3. Check status: systemctl status $APP_NAME"
log "4. View logs: journalctl -u $APP_NAME -f"
log ""
log "Service management commands:"
log "  Start:   systemctl start $APP_NAME"
log "  Stop:    systemctl stop $APP_NAME"
log "  Restart: systemctl restart $APP_NAME"
log "  Status:  systemctl status $APP_NAME"
log "  Logs:    journalctl -u $APP_NAME -f"

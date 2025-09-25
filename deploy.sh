#!/bin/bash

# Crypto TGE Monitor - Production Deployment Script
# This script handles deployment to EC2 instances

set -e  # Exit on any error

# Configuration
APP_NAME="crypto-tge-monitor"
APP_DIR="/opt/$APP_NAME"
SERVICE_NAME="crypto-tge-monitor"
LOG_DIR="/var/log/$APP_NAME"
STATE_DIR="/var/lib/$APP_NAME"
PYTHON_VERSION="3.11"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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
check_root() {
    if [[ $EUID -ne 0 ]]; then
        error "This script must be run as root"
    fi
}

# Install system dependencies
install_system_deps() {
    log "Installing system dependencies..."

    # Update package list
    apt-get update -q

    # Install Python and pip
    apt-get install -y python${PYTHON_VERSION} python${PYTHON_VERSION}-pip python${PYTHON_VERSION}-venv

    # Install git for deployment
    apt-get install -y git

    # Install supervisor for process management
    apt-get install -y supervisor

    log "System dependencies installed successfully"
}

# Create application user
create_app_user() {
    log "Creating application user..."

    if ! id "$APP_NAME" &>/dev/null; then
        useradd --system --shell /bin/bash --home-dir $APP_DIR --create-home $APP_NAME
        log "Created user: $APP_NAME"
    else
        log "User $APP_NAME already exists"
    fi
}

# Create directories with proper permissions
create_directories() {
    log "Creating application directories..."

    # Create directories
    mkdir -p $APP_DIR $LOG_DIR $STATE_DIR

    # Set ownership
    chown -R $APP_NAME:$APP_NAME $APP_DIR $LOG_DIR $STATE_DIR

    # Set permissions
    chmod 755 $APP_DIR
    chmod 755 $LOG_DIR
    chmod 750 $STATE_DIR

    log "Directories created successfully"
}

# Deploy application code
deploy_code() {
    log "Deploying application code..."

    # Stop service if running
    if systemctl is-active --quiet $SERVICE_NAME; then
        log "Stopping $SERVICE_NAME service..."
        systemctl stop $SERVICE_NAME
    fi

    # Backup current deployment if it exists
    if [ -d "$APP_DIR/current" ]; then
        log "Backing up current deployment..."
        mv $APP_DIR/current $APP_DIR/backup-$(date +%Y%m%d_%H%M%S) || true
    fi

    # Create new deployment directory
    mkdir -p $APP_DIR/current

    # Copy application files (assuming we're running from repo root)
    cp -r src/ $APP_DIR/current/
    cp config.py $APP_DIR/current/
    cp requirements.txt $APP_DIR/current/
    cp CLAUDE.md $APP_DIR/current/

    # Set ownership
    chown -R $APP_NAME:$APP_NAME $APP_DIR/current

    log "Application code deployed successfully"
}

# Setup Python virtual environment
setup_virtualenv() {
    log "Setting up Python virtual environment..."

    # Switch to app user for venv creation
    sudo -u $APP_NAME python${PYTHON_VERSION} -m venv $APP_DIR/venv

    # Activate venv and install dependencies
    sudo -u $APP_NAME $APP_DIR/venv/bin/pip install --upgrade pip
    sudo -u $APP_NAME $APP_DIR/venv/bin/pip install -r $APP_DIR/current/requirements.txt

    log "Virtual environment setup complete"
}

# Create systemd service
create_service() {
    log "Creating systemd service..."

    cat > /etc/systemd/system/$SERVICE_NAME.service << EOF
[Unit]
Description=Crypto TGE Monitor
After=network.target
Wants=network.target

[Service]
Type=simple
User=$APP_NAME
Group=$APP_NAME
WorkingDirectory=$APP_DIR/current
Environment=PYTHONPATH=$APP_DIR/current
ExecStart=$APP_DIR/venv/bin/python src/main.py --mode continuous
ExecReload=/bin/kill -HUP \$MAINPID
Restart=always
RestartSec=10
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=$SERVICE_NAME

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$LOG_DIR $STATE_DIR

# Environment file
EnvironmentFile=-$APP_DIR/.env

[Install]
WantedBy=multi-user.target
EOF

    # Reload systemd and enable service
    systemctl daemon-reload
    systemctl enable $SERVICE_NAME

    log "Systemd service created and enabled"
}

# Setup log rotation
setup_logrotate() {
    log "Setting up log rotation..."

    cat > /etc/logrotate.d/$APP_NAME << EOF
$LOG_DIR/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 $APP_NAME $APP_NAME
    postrotate
        systemctl reload $SERVICE_NAME > /dev/null 2>&1 || true
    endscript
}
EOF

    log "Log rotation configured"
}

# Setup environment file template
setup_env_template() {
    log "Setting up environment file template..."

    if [ ! -f "$APP_DIR/.env" ]; then
        cat > $APP_DIR/.env << 'EOF'
# Email Configuration (Required)
EMAIL_USER=your-email@gmail.com
EMAIL_PASSWORD=your-app-password
RECIPIENT_EMAIL=recipient@example.com
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587

# Twitter API Configuration (Optional)
TWITTER_BEARER_TOKEN=your-bearer-token

# Logging Configuration (Optional)
LOG_LEVEL=INFO
LOG_FILE=/var/log/crypto-tge-monitor/crypto_monitor.log

# System Configuration
DISABLE_TWITTER=0
TWITTER_ENABLE_SEARCH=1
EOF

        chown $APP_NAME:$APP_NAME $APP_DIR/.env
        chmod 600 $APP_DIR/.env

        warn "Environment file created at $APP_DIR/.env - PLEASE UPDATE WITH YOUR CREDENTIALS"
    else
        log "Environment file already exists"
    fi
}

# Start services
start_services() {
    log "Starting services..."

    systemctl start $SERVICE_NAME
    systemctl status $SERVICE_NAME --no-pager -l

    log "Service started successfully"
}

# Main deployment function
main() {
    log "Starting Crypto TGE Monitor deployment..."

    check_root
    install_system_deps
    create_app_user
    create_directories
    deploy_code
    setup_virtualenv
    create_service
    setup_logrotate
    setup_env_template
    start_services

    log "Deployment completed successfully!"
    echo
    echo -e "${BLUE}Next steps:${NC}"
    echo "1. Edit $APP_DIR/.env with your configuration"
    echo "2. Restart the service: systemctl restart $SERVICE_NAME"
    echo "3. Check logs: journalctl -u $SERVICE_NAME -f"
    echo "4. Check status: systemctl status $SERVICE_NAME"
    echo
    echo -e "${GREEN}Service is now running and will start automatically on boot.${NC}"
}

# Run main function
main "$@"
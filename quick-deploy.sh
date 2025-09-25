#!/bin/bash

# Crypto TGE Monitor - Quick Deploy Script for Ubuntu
set -e

APP_NAME="crypto-tge-monitor"
APP_DIR="/opt/$APP_NAME"

echo "🚀 Starting Quick Deployment..."

# Update system
echo "📦 Updating system packages..."
sudo apt-get update -q

# Install Python and dependencies
echo "🐍 Installing Python..."
sudo apt-get install -y python3 python3-pip python3-venv git

# Create app user
echo "👤 Creating application user..."
if ! id "$APP_NAME" &>/dev/null; then
    sudo useradd --system --shell /bin/bash --home-dir $APP_DIR --create-home $APP_NAME
fi

# Create directories
echo "📁 Creating directories..."
sudo mkdir -p $APP_DIR /var/log/$APP_NAME /var/lib/$APP_NAME
sudo chown -R $APP_NAME:$APP_NAME $APP_DIR /var/log/$APP_NAME /var/lib/$APP_NAME

# Clone repository
echo "📥 Cloning repository..."
sudo -u $APP_NAME git clone https://github.com/mellis-netizen/Twitter_Scraper.git $APP_DIR/current

# Create virtual environment
echo "🔧 Setting up Python environment..."
sudo -u $APP_NAME python3 -m venv $APP_DIR/venv

# Install dependencies
echo "📚 Installing Python packages..."
sudo -u $APP_NAME $APP_DIR/venv/bin/pip install --upgrade pip
sudo -u $APP_NAME $APP_DIR/venv/bin/pip install -r $APP_DIR/current/requirements.txt

# Create systemd service
echo "⚙️ Creating systemd service..."
sudo tee /etc/systemd/system/$APP_NAME.service > /dev/null << EOF
[Unit]
Description=Crypto TGE Monitor
After=network.target

[Service]
Type=simple
User=$APP_NAME
Group=$APP_NAME
WorkingDirectory=$APP_DIR/current
Environment=PYTHONPATH=$APP_DIR/current
ExecStart=$APP_DIR/venv/bin/python src/main.py --mode continuous
Restart=always
RestartSec=10
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=$APP_NAME

# Environment file
EnvironmentFile=-$APP_DIR/.env

[Install]
WantedBy=multi-user.target
EOF

# Enable service
sudo systemctl daemon-reload
sudo systemctl enable $APP_NAME

# Create environment file template
if [ ! -f "$APP_DIR/.env" ]; then
    echo "📝 Creating environment file template..."
    sudo tee $APP_DIR/.env > /dev/null << 'EOF'
# Email Configuration (Required)
EMAIL_USER=your-email@gmail.com
EMAIL_PASSWORD=your-app-password
RECIPIENT_EMAIL=recipient@example.com
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587

# Twitter API Configuration (Optional)
TWITTER_BEARER_TOKEN=your-bearer-token

# Logging Configuration
LOG_LEVEL=INFO
LOG_FILE=/var/log/crypto-tge-monitor/crypto_monitor.log
EOF

    sudo chown $APP_NAME:$APP_NAME $APP_DIR/.env
    sudo chmod 600 $APP_DIR/.env
fi

echo ""
echo "✅ Deployment completed!"
echo ""
echo "🔧 Next steps:"
echo "1. Edit the configuration: sudo nano $APP_DIR/.env"
echo "2. Start the service: sudo systemctl start $APP_NAME"
echo "3. Check status: sudo systemctl status $APP_NAME"
echo "4. View logs: sudo journalctl -u $APP_NAME -f"
echo ""
echo "🎉 Ready for automatic deployments!"
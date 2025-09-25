# Deployment Instructions

## Initial EC2 Setup (Run Once)

1. **SSH into your EC2 instance:**
   ```bash
   ssh -i your-key.pem ubuntu@3.133.23.229
   ```

2. **Copy and run the quick deployment script:**
   ```bash
   # Download the script
   curl -o quick-deploy.sh https://raw.githubusercontent.com/mellis-netizen/Twitter_Scraper/main/quick-deploy.sh

   # Make it executable and run
   chmod +x quick-deploy.sh
   sudo ./quick-deploy.sh
   ```

3. **Configure your environment:**
   ```bash
   sudo nano /opt/crypto-tge-monitor/.env
   ```

   Update with your actual credentials:
   - EMAIL_USER=your-actual-email@gmail.com
   - EMAIL_PASSWORD=your-app-password
   - RECIPIENT_EMAIL=where-to-send-alerts@domain.com
   - TWITTER_BEARER_TOKEN=your-twitter-token (optional)

4. **Start the service:**
   ```bash
   sudo systemctl restart crypto-tge-monitor
   sudo systemctl status crypto-tge-monitor
   ```

## Automatic Updates

Once the initial setup is complete, any push to the `main` branch will automatically:
- Pull the latest code
- Update dependencies
- Restart the service
- Verify it's running

## Monitoring

```bash
# Check service status
sudo systemctl status crypto-tge-monitor

# View logs
sudo journalctl -u crypto-tge-monitor -f

# View application logs
sudo tail -f /var/log/crypto-tge-monitor/crypto_monitor.log
```

## Troubleshooting

If the GitHub Actions deployment fails, check:
1. Service was initially set up (run quick-deploy.sh first)
2. Virtual environment exists
3. User `crypto-tge-monitor` was created
4. Environment file is configured

**Note:** The GitHub Actions workflow now includes better error checking and will tell you if the initial setup needs to be run.
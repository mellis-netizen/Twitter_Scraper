# 🚀 Crypto TGE Monitor

A production-ready monitoring system for cryptocurrency Token Generation Events (TGEs) that tracks news sources and Twitter for TGE announcements and sends email alerts.

## ✨ Features

- **📰 News Monitoring**: Scrapes RSS feeds from major crypto news sources
- **🐦 Twitter Monitoring**: Tracks crypto Twitter accounts and searches for TGE-related content
- **🔍 Smart Analysis**: Uses NLP and keyword matching to identify TGE-related content
- **📧 Email Alerts**: Sends formatted email notifications when TGE events are detected
- **⏰ Scheduled Monitoring**: Runs continuously with configurable intervals
- **📊 Relevance Scoring**: Ranks content by relevance to TGE events
- **🏢 Company Tracking**: Monitors specific companies for TGE announcements
- **🛡️ Production Ready**: Comprehensive error handling, retry logic, and monitoring
- **💾 Data Persistence**: State management and deduplication
- **🏥 Health Monitoring**: Built-in health checks and system monitoring
- **🐳 Docker Support**: Containerized deployment with Docker Compose
- **🔧 Systemd Integration**: Native Linux service management

## 🚀 Quick Start

### Option 1: Docker Deployment (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd crypto-tge-monitor

# Configure environment
cp env.template .env
nano .env  # Edit with your settings

# Start with Docker Compose
docker-compose up -d

# Check status
docker-compose logs -f
```

### Option 2: Manual Installation

```bash
# Clone the repository
git clone <repository-url>
cd crypto-tge-monitor

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp env.template .env
nano .env  # Edit with your settings

# Test the system
python src/main.py --mode test

# Run continuously
python src/main.py --mode continuous
```

### Option 3: Production Deployment

```bash
# Clone the repository
git clone <repository-url>
cd crypto-tge-monitor

# Run deployment script (requires root)
sudo ./scripts/deploy.sh

# Configure environment
sudo nano /opt/crypto-tge-monitor/.env

# Start the service
sudo systemctl start crypto-tge-monitor

# Check status
sudo systemctl status crypto-tge-monitor
```

## Configuration

### Email Setup (Required)

For Gmail:
1. Enable 2-factor authentication
2. Generate an App Password
3. Use your Gmail address and the app password in `.env`

```env
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
EMAIL_USER=your-email@gmail.com
EMAIL_PASSWORD=your-app-password
RECIPIENT_EMAIL=recipient@example.com
```

### Twitter API Setup (Optional)

1. Apply for Twitter Developer access at https://developer.twitter.com/
2. Create a new app and generate API keys
3. Add the credentials to `.env`

```env
TWITTER_API_KEY=your-twitter-api-key
TWITTER_API_SECRET=your-twitter-api-secret
TWITTER_ACCESS_TOKEN=your-twitter-access-token
TWITTER_ACCESS_TOKEN_SECRET=your-twitter-access-token-secret
TWITTER_BEARER_TOKEN=your-twitter-bearer-token
```

## Monitored Companies

The system monitors the following companies for TGE events:

- Corn, Corn2, Curvance, Darkbright, Fabric, Caldera
- Open Eden, XAI, Espresso, 2046 Angels Ltd, Clique
- TreasureDAO, Camelot, DuckChain, Spacecoin
- FhenixToken, USD.ai, Huddle01, Succinct

## TGE Keywords

The system looks for these keywords in content:

- TGE, token generation event, token launch, token release
- token distribution, airdrop, token sale, ICO, IDO
- token listing, token launch date, token generation
- token deployment, token minting, token creation

## News Sources

The system monitors RSS feeds from:

- CoinTelegraph, Decrypt, CoinDesk, CryptoNews
- The Block, CoinGape, U.Today, CryptoSlate
- Bitcoinist, CryptoDaily

## Twitter Accounts

The system monitors these Twitter accounts:

- @cointelegraph, @decryptmedia, @CoinDesk
- @CryptoNews, @TheBlock__, @CoinGape
- @Utoday_en, @CryptoSlate, @Bitcoinist, @CryptoDaily

## 🎮 Usage Examples

### Development Mode
```bash
# Run once
python src/main.py --mode once

# Run continuously
python src/main.py --mode continuous

# Test components
python src/main.py --mode test

# Check status
python src/main.py --mode status

# Verbose logging
python src/main.py --mode continuous --verbose
```

### Production Management

#### Using the Management Script
```bash
# Service management
./scripts/monitor.sh start
./scripts/monitor.sh stop
./scripts/monitor.sh restart
./scripts/monitor.sh status

# Monitoring and diagnostics
./scripts/monitor.sh logs          # Follow logs
./scripts/monitor.sh logs-tail     # Last 100 lines
./scripts/monitor.sh test          # Run system test
./scripts/monitor.sh health        # Health check
./scripts/monitor.sh stats         # Show statistics

# Maintenance
./scripts/monitor.sh backup        # Backup data
./scripts/monitor.sh update        # Update application
```

#### Using Systemd (Production)
```bash
# Service management
sudo systemctl start crypto-tge-monitor
sudo systemctl stop crypto-tge-monitor
sudo systemctl restart crypto-tge-monitor
sudo systemctl status crypto-tge-monitor

# View logs
sudo journalctl -u crypto-tge-monitor -f
sudo journalctl -u crypto-tge-monitor --since "1 hour ago"
```

#### Using Docker Compose
```bash
# Service management
docker-compose up -d               # Start in background
docker-compose down                # Stop and remove containers
docker-compose restart             # Restart services
docker-compose ps                  # Show status

# View logs
docker-compose logs -f             # Follow logs
docker-compose logs --tail=100     # Last 100 lines

# Execute commands
docker-compose exec crypto-tge-monitor python src/main.py --mode status
```

## Email Alerts

When TGE-related content is detected, you'll receive email alerts with:

- **News Alerts**: Article title, source, companies mentioned, TGE keywords, relevance score
- **Twitter Alerts**: Tweet content, user info, engagement metrics, relevance analysis
- **Daily Summary**: Overview of daily monitoring activity

## Logging

Logs are written to `logs/crypto_monitor.log` and include:

- Monitoring cycle results
- TGE alerts found
- Error messages and debugging info
- System status updates

## Architecture

```
src/
├── main.py              # Main application runner
├── news_scraper.py      # RSS feed monitoring and analysis
├── twitter_monitor.py   # Twitter API integration
└── email_notifier.py    # Email notification system

config.py                # Configuration and constants
requirements.txt         # Python dependencies
env.template            # Environment variables template
```

## Dependencies

- `requests` - HTTP requests
- `beautifulsoup4` - HTML parsing
- `selenium` - Web scraping (if needed)
- `tweepy` - Twitter API
- `schedule` - Task scheduling
- `python-dotenv` - Environment variables
- `feedparser` - RSS feed parsing
- `newspaper3k` - Article content extraction
- `nltk` - Natural language processing
- `textblob` - Text analysis
- `pandas` - Data manipulation

## Troubleshooting

### Common Issues

1. **Email not sending**: Check SMTP credentials and app password
2. **Twitter errors**: Verify API credentials and rate limits
3. **No TGE alerts**: Check if companies/keywords are being mentioned
4. **RSS feed errors**: Some feeds may be temporarily unavailable

### Debug Mode

Run with verbose logging to see detailed information:

```bash
python src/main.py --mode continuous --verbose
```

### Test Individual Components

```bash
# Test news scraper only
python src/news_scraper.py

# Test Twitter monitor only
python src/twitter_monitor.py

# Test email notifier only
python src/email_notifier.py
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License.

## Support

For issues and questions:
1. Check the logs in `logs/crypto_monitor.log`
2. Run in test mode to verify configuration
3. Check the troubleshooting section above
4. Open an issue on GitHub

---

**Happy TGE Hunting! 🚀**


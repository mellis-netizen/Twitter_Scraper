# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a production-ready cryptocurrency Token Generation Event (TGE) monitoring system. It continuously monitors news sources and Twitter for TGE-related announcements from specific companies and sends email alerts when relevant content is detected.

## Core Commands

### Running the Application
```bash
# Run a single monitoring cycle
python src/main.py --mode once

# Run continuously (production mode)
python src/main.py --mode continuous

# Test all components
python src/main.py --mode test

# Check system status
python src/main.py --mode status

# Run with verbose logging
python src/main.py --mode continuous --verbose
```

### Testing and Development
```bash
# Run tests (if test framework is available)
python run_tests.py

# Test the full system integration
python test_full_system.py

# Run system with Twitter enabled
python run_system_with_twitter.py

# Run system without Twitter
python run_system.py
```

### Dependencies Management
```bash
# Install dependencies
pip install -r requirements.txt

# Check for missing dependencies
python -c "import requests, feedparser, schedule, tweepy, psutil; print('All dependencies available')"
```

## Architecture Overview

### Core Components

**Main Application (`src/main.py`)**
- Orchestrates the entire system using the `CryptoTGEMonitor` class
- Manages scheduling (every 30 minutes), error handling, and graceful shutdown
- Implements circuit breakers and watchdog mechanisms for reliability
- Handles deduplication using persistent state in `state/seen.json`
- Provides comprehensive health monitoring and metrics tracking

**News Scraper (`src/news_scraper.py`)**
- Fetches RSS feeds from ~50 crypto news sources
- Uses robust HTTP session with retries and connection pooling
- Implements URL normalization for Medium, Ghost, and other blog platforms
- Features circuit breaker pattern for failed feeds
- Caches processed articles to avoid reprocessing

**Twitter Monitor (`src/twitter_monitor.py`)**
- Monitors Twitter timelines and performs targeted searches
- Uses Twitter API v2 with bearer token authentication
- Implements incremental fetching with `since_id` persistence
- Features backoff logic for rate limiting
- Searches for company + TGE keyword combinations

**Email Notifier (`src/email_notifier.py`)**
- Sends rich HTML email alerts with embedded CSS
- Supports multiple SMTP configurations (Gmail, custom servers)
- Implements retry logic with exponential backoff
- Sends daily summaries at 9 AM PST
- Validates all inputs to prevent injection attacks

**Configuration (`config.py`)**
- Centralizes all configuration including companies, keywords, news sources
- Validates environment variables and API credentials
- Contains ~20 monitored companies with aliases
- Defines 30+ TGE-related keywords with sophisticated matching

### Key Design Patterns

**Sophisticated Content Matching**
The system uses multi-strategy matching logic:
1. Company name AND TGE keyword in same text
2. High-confidence TGE keywords (standalone)
3. Company name with TGE context words

**Deduplication Strategy**
- Uses SHA-1 hashes of URLs or content identifiers
- Persistent state stored in `state/seen.json`
- Prevents duplicate alerts while maintaining history

**Error Resilience**
- Circuit breaker patterns for failed RSS feeds
- Retry logic with exponential backoff
- Graceful degradation when components fail
- Timeout protection with thread executors

**State Management**
- Persistent storage in `state/` directory
- Twitter `since_id` tracking for incremental updates
- Application state persistence for metrics continuity
- Health check results tracking

## Environment Configuration

### Required Variables (.env file)
```bash
# Email (Required)
EMAIL_USER=your-email@gmail.com
EMAIL_PASSWORD=your-app-password
RECIPIENT_EMAIL=recipient@example.com
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587

# Twitter (Optional)
TWITTER_BEARER_TOKEN=your-bearer-token

# Logging (Optional)
LOG_LEVEL=INFO
LOG_FILE=logs/crypto_monitor.log
```

### Optional Environment Variables
- `DISABLE_TWITTER=1` - Disable Twitter monitoring
- `TWITTER_ENABLE_SEARCH=0` - Disable Twitter search functionality
- `TWITTER_USERS=handle1,handle2` - Override monitored Twitter accounts

## Data Persistence

**State Directory Structure**
```
state/
├── seen.json                 # Deduplication hashes
├── twitter_since.json        # Twitter pagination state
└── monitor_state.json        # Application metrics and state
```

**Log Directory Structure**
```
logs/
├── crypto_monitor.log        # Main application log (rotating)
└── crypto_monitor.log.1      # Rotated log files
```

## Monitoring and Metrics

The system tracks comprehensive metrics:
- Total articles/tweets processed
- TGE alerts sent
- Error rates and consecutive failures
- Feed health status
- Memory usage and cycle times
- Component health checks

Access via `--mode status` or monitor log files for real-time metrics.

## Testing Strategy

**Component Testing**
- Individual module tests for news scraper, Twitter monitor, email notifier
- Configuration validation tests
- SMTP connectivity tests

**Integration Testing**
- Full system end-to-end tests
- Error condition simulation
- Rate limiting and timeout testing

## Common Development Patterns

When modifying the system:

1. **Adding New News Sources**: Add RSS URLs to `NEWS_SOURCES` in `config.py`
2. **Adding Companies**: Add to `COMPANIES` list with aliases for better matching
3. **Modifying Keywords**: Update `TGE_KEYWORDS` list - test matching logic carefully
4. **Email Template Changes**: Modify `_generate_email_body()` in `email_notifier.py`
5. **Error Handling**: Follow existing retry and circuit breaker patterns

## Production Deployment

The system is designed for 24/7 operation:
- Scheduled monitoring every 30 minutes
- Daily summary emails at 9 AM PST
- Graceful shutdown handling (SIGTERM/SIGINT)
- Automatic log rotation
- Health monitoring with alerts for consecutive failures

Monitor the `logs/crypto_monitor.log` file for operational status and any issues.
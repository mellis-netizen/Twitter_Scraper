"""
Main Application Runner for Crypto TGE Monitor

This module orchestrates the entire TGE monitoring system, including
scheduling, coordination between modules, and error handling.
"""

import schedule
import time
import logging
import signal
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import os
import json
import threading
import traceback

# Import our modules
from news_scraper import NewsScraper
from twitter_monitor import TwitterMonitor
from email_notifier import EmailNotifier
from config import LOG_CONFIG, COMPANIES, TGE_KEYWORDS, validate_config
from utils import (
    setup_structured_logging, HealthChecker, retry_on_failure,
    save_json_file, load_json_file
)


class CryptoTGEMonitor:
    """Main class that orchestrates the entire TGE monitoring system."""
    
    def __init__(self):
        self.setup_logging()
        self.setup_signal_handlers()
        
        # Validate configuration
        self.validate_system_config()
        
        # Initialize components
        self.news_scraper = NewsScraper()
        self.twitter_monitor = TwitterMonitor()
        self.email_notifier = EmailNotifier()
        
        # State tracking
        self.running = True
        self.last_run_time = None
        self.total_news_processed = 0
        self.total_tweets_processed = 0
        self.total_alerts_sent = 0
        self.cycle_count = 0
        self.error_count = 0
        
        # Health monitoring
        self.health_checker = HealthChecker()
        self.setup_health_checks()
        
        # Load state from file if it exists
        self.load_state()
        
        self.logger.info("Crypto TGE Monitor initialized successfully")
        self.logger.info(f"Monitoring {len(COMPANIES)} companies and {len(TGE_KEYWORDS)} TGE keywords")
    
    def setup_logging(self):
        """Setup logging configuration."""
        self.logger = setup_structured_logging(
            LOG_CONFIG['file'],
            LOG_CONFIG['level']
        )
    
    def validate_system_config(self):
        """Validate system configuration."""
        validation_results = validate_config()
        
        critical_components = ['email_config', 'companies_config', 'sources_config']
        failed_components = [comp for comp in critical_components if not validation_results.get(comp, False)]
        
        if failed_components:
            self.logger.error(f"Critical configuration issues: {failed_components}")
            self.logger.error("Please check your configuration and try again")
            sys.exit(1)
        
        optional_components = ['twitter_config']
        for comp in optional_components:
            if not validation_results.get(comp, False):
                self.logger.warning(f"Optional component not configured: {comp}")
        
        self.logger.info("Configuration validation passed")
    
    def setup_health_checks(self):
        """Setup health checks for system components."""
        def check_news_scraper():
            try:
                # Simple test to see if news scraper can initialize
                return hasattr(self.news_scraper, 'session')
            except Exception:
                return False
        
        def check_twitter_monitor():
            try:
                # Check if Twitter API is available (optional)
                return True  # Twitter is optional
            except Exception:
                return False
        
        def check_email_notifier():
            try:
                return self.email_notifier.enabled
            except Exception:
                return False
        
        self.health_checker.register_check(
            'news_scraper', check_news_scraper, 'News scraper component'
        )
        self.health_checker.register_check(
            'twitter_monitor', check_twitter_monitor, 'Twitter monitor component'
        )
        self.health_checker.register_check(
            'email_notifier', check_email_notifier, 'Email notification system'
        )
    
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, shutting down gracefully...")
            self.running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def load_state(self):
        """Load application state from file."""
        state_file = 'logs/monitor_state.json'
        try:
            if os.path.exists(state_file):
                with open(state_file, 'r') as f:
                    state = json.load(f)
                    self.last_run_time = datetime.fromisoformat(state.get('last_run_time', '')) if state.get('last_run_time') else None
                    self.total_news_processed = state.get('total_news_processed', 0)
                    self.total_tweets_processed = state.get('total_tweets_processed', 0)
                    self.total_alerts_sent = state.get('total_alerts_sent', 0)
                self.logger.info("Application state loaded successfully")
        except Exception as e:
            self.logger.warning(f"Failed to load application state: {str(e)}")
    
    def save_state(self):
        """Save application state to file."""
        state_file = 'logs/monitor_state.json'
        try:
            state = {
                'last_run_time': self.last_run_time.isoformat() if self.last_run_time else None,
                'total_news_processed': self.total_news_processed,
                'total_tweets_processed': self.total_tweets_processed,
                'total_alerts_sent': self.total_alerts_sent,
                'last_updated': datetime.now().isoformat()
            }
            with open(state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save application state: {str(e)}")
    
    @retry_on_failure(max_retries=2, delay=30.0, exceptions=(Exception,))
    def run_monitoring_cycle(self):
        """Run a complete monitoring cycle."""
        start_time = datetime.now()
        self.cycle_count += 1
        
        self.logger.info(f"Starting monitoring cycle #{self.cycle_count}...")
        
        try:
            news_alerts = []
            twitter_alerts = []
            
            # Process news articles with error handling
            try:
                self.logger.info("Processing news articles...")
                news_alerts = self.news_scraper.process_articles()
                self.total_news_processed += len(news_alerts)
                self.logger.info(f"News processing completed: {len(news_alerts)} alerts found")
            except Exception as e:
                self.logger.error(f"Error processing news articles: {str(e)}", exc_info=True)
                self.error_count += 1
            
            # Process Twitter content with error handling
            try:
                self.logger.info("Processing Twitter content...")
                twitter_alerts = self.twitter_monitor.process_tweets()
                self.total_tweets_processed += len(twitter_alerts)
                self.logger.info(f"Twitter processing completed: {len(twitter_alerts)} alerts found")
            except Exception as e:
                self.logger.error(f"Error processing Twitter content: {str(e)}", exc_info=True)
                self.error_count += 1
            
            # Send email alerts if any TGE content found
            if news_alerts or twitter_alerts:
                self.logger.info(f"Sending email alerts: {len(news_alerts)} news, {len(twitter_alerts)} Twitter")
                try:
                    if self.email_notifier.send_tge_alert_email(news_alerts, twitter_alerts):
                        self.total_alerts_sent += 1
                        self.logger.info("Email alerts sent successfully")
                    else:
                        self.logger.error("Failed to send email alerts")
                        self.error_count += 1
                except Exception as e:
                    self.logger.error(f"Error sending email alerts: {str(e)}", exc_info=True)
                    self.error_count += 1
            else:
                self.logger.info("No TGE alerts found in this cycle")
            
            # Update state
            self.last_run_time = start_time
            self.save_state()
            
            # Log cycle summary
            cycle_duration = (datetime.now() - start_time).total_seconds()
            self.logger.info(
                f"Monitoring cycle #{self.cycle_count} completed in {cycle_duration:.2f}s - "
                f"Found {len(news_alerts)} news alerts, {len(twitter_alerts)} Twitter alerts"
            )
            
        except Exception as e:
            self.logger.error(f"Critical error in monitoring cycle: {str(e)}", exc_info=True)
            self.error_count += 1
            raise
    
    def send_daily_summary(self):
        """Send daily summary email."""
        self.logger.info("Sending daily summary...")
        try:
            self.email_notifier.send_daily_summary(
                news_count=len(self.news_scraper.get_recent_tge_articles(24)),
                twitter_count=len(self.twitter_monitor.get_recent_tge_tweets(24)),
                total_processed=self.total_news_processed + self.total_tweets_processed
            )
        except Exception as e:
            self.logger.error(f"Failed to send daily summary: {str(e)}")
    
    def setup_schedule(self):
        """Setup the monitoring schedule."""
        # Run monitoring every 30 minutes
        schedule.every(30).minutes.do(self.run_monitoring_cycle)
        
        # Send daily summary at 9 AM UTC
        schedule.every().day.at("09:00").do(self.send_daily_summary)
        
        # Log schedule info
        self.logger.info("Schedule configured:")
        self.logger.info("- Monitoring cycle: Every 30 minutes")
        self.logger.info("- Daily summary: 9:00 AM UTC")
    
    def run_once(self):
        """Run a single monitoring cycle and exit."""
        self.logger.info("Running single monitoring cycle...")
        self.run_monitoring_cycle()
        self.logger.info("Single cycle completed")
    
    def run_continuous(self):
        """Run the monitoring system continuously."""
        self.logger.info("Starting continuous monitoring...")
        self.setup_schedule()
        
        # Run initial cycle
        self.run_monitoring_cycle()
        
        # Main loop
        while self.running:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except KeyboardInterrupt:
                self.logger.info("Received keyboard interrupt, shutting down...")
                break
            except Exception as e:
                self.logger.error(f"Error in main loop: {str(e)}", exc_info=True)
                time.sleep(60)  # Wait before retrying
        
        self.logger.info("Monitoring stopped")
    
    def test_components(self):
        """Test all components individually."""
        self.logger.info("Testing all components...")
        
        # Test news scraper
        try:
            self.logger.info("Testing news scraper...")
            news_alerts = self.news_scraper.process_articles()
            self.logger.info(f"✅ News scraper: Found {len(news_alerts)} alerts")
        except Exception as e:
            self.logger.error(f"❌ News scraper failed: {str(e)}")
        
        # Test Twitter monitor
        try:
            self.logger.info("Testing Twitter monitor...")
            twitter_alerts = self.twitter_monitor.process_tweets()
            self.logger.info(f"✅ Twitter monitor: Found {len(twitter_alerts)} alerts")
        except Exception as e:
            self.logger.error(f"❌ Twitter monitor failed: {str(e)}")
        
        # Test email notifier
        try:
            self.logger.info("Testing email notifier...")
            if self.email_notifier.send_test_email():
                self.logger.info("✅ Email notifier: Test email sent successfully")
            else:
                self.logger.error("❌ Email notifier: Failed to send test email")
        except Exception as e:
            self.logger.error(f"❌ Email notifier failed: {str(e)}")
        
        self.logger.info("Component testing completed")
    
    def get_status(self):
        """Get current system status."""
        # Run health checks
        health_status = self.health_checker.get_overall_status()
        
        # Get component stats
        news_stats = self.news_scraper.get_stats()
        twitter_stats = self.twitter_monitor.get_stats()
        
        status = {
            'running': self.running,
            'last_run_time': self.last_run_time.isoformat() if self.last_run_time else None,
            'cycle_count': self.cycle_count,
            'error_count': self.error_count,
            'health_status': health_status,
            'total_news_processed': self.total_news_processed,
            'total_tweets_processed': self.total_tweets_processed,
            'total_alerts_sent': self.total_alerts_sent,
            'companies_monitored': len(COMPANIES),
            'tge_keywords': len(TGE_KEYWORDS),
            'email_enabled': self.email_notifier.enabled,
            'twitter_enabled': self.twitter_monitor.api is not None,
            'news_stats': news_stats,
            'twitter_stats': twitter_stats,
            'uptime': str(datetime.now() - self.last_run_time) if self.last_run_time else None
        }
        return status
    
    def print_status(self):
        """Print current system status."""
        status = self.get_status()
        print("\n" + "="*60)
        print("🚀 CRYPTO TGE MONITOR STATUS")
        print("="*60)
        print(f"Status: {'🟢 Running' if status['running'] else '🔴 Stopped'}")
        print(f"Health: {status['health_status'].upper()}")
        print(f"Last Run: {status['last_run_time'] or 'Never'}")
        print(f"Cycles Completed: {status['cycle_count']}")
        print(f"Errors: {status['error_count']}")
        print(f"Companies Monitored: {status['companies_monitored']}")
        print(f"TGE Keywords: {status['tge_keywords']}")
        print(f"Total News Processed: {status['total_news_processed']}")
        print(f"Total Tweets Processed: {status['total_tweets_processed']}")
        print(f"Total Alerts Sent: {status['total_alerts_sent']}")
        print(f"Email Notifications: {'✅ Enabled' if status['email_enabled'] else '❌ Disabled'}")
        print(f"Twitter Monitoring: {'✅ Enabled' if status['twitter_enabled'] else '❌ Disabled'}")
        
        # Component stats
        print("\n📊 COMPONENT STATISTICS:")
        print(f"News - Processed: {status['news_stats']['total_processed']}, TGE: {status['news_stats']['total_tge_articles']}")
        print(f"Twitter - Processed: {status['twitter_stats']['total_processed']}, TGE: {status['twitter_stats']['total_tge_tweets']}")
        
        print("="*60 + "\n")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Crypto TGE Monitor')
    parser.add_argument('--mode', choices=['once', 'continuous', 'test', 'status'], 
                       default='continuous', help='Run mode')
    parser.add_argument('--verbose', '-v', action='store_true', 
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Adjust logging level if verbose
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create monitor instance
    monitor = CryptoTGEMonitor()
    
    try:
        if args.mode == 'once':
            monitor.run_once()
        elif args.mode == 'continuous':
            monitor.run_continuous()
        elif args.mode == 'test':
            monitor.test_components()
        elif args.mode == 'status':
            monitor.print_status()
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Fatal error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()

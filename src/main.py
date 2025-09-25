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
from datetime import datetime, timezone
from typing import List, Dict, Optional
import os, json, re, hashlib
import threading
import traceback

# Import our modules
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from src.news_scraper import NewsScraper
from src.email_notifier import EmailNotifier
from src.twitter_monitor import TwitterMonitor
from config import COMPANIES, NEWS_SOURCES, LOG_CONFIG, TGE_KEYWORDS
from src.utils import setup_structured_logging, HealthChecker, retry_on_failure

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

# ----------------------------------------------------------------------
# Run-with-timeout helper
# ----------------------------------------------------------------------
def run_with_timeout(fn, *args, timeout: float = 45.0, logger=None, **kwargs):
    """
    Run a function in a thread and enforce a hard timeout.
    Returns (ok, result_or_exception). If ok=False and result is None -> timed out.
    """
    try:
        with ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(fn, *args, **kwargs)
            return True, fut.result(timeout=timeout)
    except FuturesTimeoutError:
        if logger:
            logger.warning(f"{getattr(fn, '__name__', 'call')} timed out after {timeout}s; skipping this cycle.")
        return False, None
    except Exception as e:
        if logger:
            logger.error(f"Error in {getattr(fn, '__name__', 'call')}: {e}", exc_info=True)
        return False, e

# ----------------------------------------------------------------------
# De-dupe state: keep a set of seen alert keys on disk
# ----------------------------------------------------------------------
STATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "state")
SEEN_PATH = os.path.join(STATE_DIR, "seen.json")

def _text_from_alert(alert: dict) -> str:
    parts = [
        alert.get("title", ""),
        alert.get("summary", ""),
        alert.get("text", ""),
        alert.get("content", ""),
    ]
    return " ".join([p for p in parts if p]).strip()

def matches_company_and_keyword(alert: dict) -> bool:
    """
    Flexible matching: require either:
    1. Company name AND keyword in same text, OR
    2. Strong TGE keyword with high confidence, OR  
    3. Company name with TGE context words
    """
    # Validate alert structure
    if not isinstance(alert, dict):
        return False
    
    text = _text_from_alert(alert).lower()
    if not text or len(text.strip()) < 10:  # Minimum text length
        return False
    
    # Quality checks
    if len(text) > 50000:  # Too long, likely spam
        return False

    def _has(token: str) -> bool:
        token = re.escape(token.strip())
        return re.search(rf"\b{token}\b", text, flags=re.IGNORECASE) is not None

    def _company_hit() -> bool:
        for c in COMPANIES:
            if isinstance(c, dict):
                names = [c.get("name","")] + c.get("aliases", [])
            else:
                names = [str(c)]
            if any(_has(n) for n in names if n):
                return True
        return False

    def _keyword_hit() -> bool:
        return any(_has(k) for k in TGE_KEYWORDS)

    def _strong_tge_keywords() -> bool:
        """High-confidence TGE keywords that don't need company match"""
        strong_keywords = [
            "token generation event", "tge", "token launch", "token release",
            "airdrop", "token sale", "ico", "ido", "token distribution"
        ]
        return any(_has(k) for k in strong_keywords)

    def _tge_context_words() -> bool:
        """Context words that suggest TGE when combined with company"""
        context_words = [
            "launch", "release", "deploy", "mint", "create", "generate",
            "announce", "coming", "soon", "date", "schedule", "timeline"
        ]
        return any(_has(w) for w in context_words)

    # Strategy 1: Company + keyword (original logic)
    if _company_hit() and _keyword_hit():
        return True
    
    # Strategy 2: Strong TGE keywords (high confidence standalone)
    if _strong_tge_keywords():
        return True
    
    # Strategy 3: Company + TGE context words
    if _company_hit() and _tge_context_words():
        return True

    return False

def alert_key(alert: dict) -> str:
    """
    Stable ID for de-dup: prefer URL; else title+source+date.
    """
    basis = (
        alert.get("url")
        or f"{alert.get('title','')}|{alert.get('source','')}|{alert.get('published','')}"
    )
    return hashlib.sha1(basis.encode("utf-8", errors="ignore")).hexdigest()

def load_seen() -> set[str]:
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        if os.path.isfile(SEEN_PATH):
            with open(SEEN_PATH, "r", encoding="utf-8") as f:
                return set(json.load(f))
    except Exception as e:
        logging.getLogger(__name__).warning(f"Failed to load seen alerts: {e}")
    return set()

def save_seen(seen: set[str]) -> None:
    os.makedirs(STATE_DIR, exist_ok=True)
    tmp = SEEN_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f, ensure_ascii=False, indent=2)
    os.replace(tmp, SEEN_PATH)

def filter_and_dedupe(alerts: list[dict]) -> tuple[list[dict], set[str]]:
    seen = load_seen()
    out = []
    for a in alerts:
        if not matches_company_and_keyword(a):
            continue
        k = alert_key(a)
        if k in seen:
            continue
        out.append(a)
        seen.add(k)
    return out, seen

# ----------------------------------------------------------------------
# Config validation
# ----------------------------------------------------------------------
def validate_config() -> dict:
    ok = {}
    ok['companies_config'] = isinstance(COMPANIES, list) and len(COMPANIES) > 0
    ok['sources_config']   = isinstance(NEWS_SOURCES, list) and len(NEWS_SOURCES) > 0
    ok['email_config']     = True
    ok['twitter_config']   = True
    return ok

# ----------------------------------------------------------------------
# Main monitor
# ----------------------------------------------------------------------
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
        self._last_twitter_processed = 0  # Track Twitter processing for accurate stats
        
        # Enhanced metrics
        self.start_time = datetime.now(timezone.utc)
        self.cycle_times = []  # Track cycle durations
        self.feed_failures = {}  # Track feed failure counts
        self.api_errors = {}  # Track API error counts
        self.memory_usage = []  # Track memory usage
        
        # Watchdog mechanism
        self.last_successful_cycle = None
        self.consecutive_failures = 0
        self.max_consecutive_failures = 5
        
        # Circuit breaker reset mechanism
        self.circuit_breaker_reset_time = 3600  # 1 hour
        self.last_circuit_breaker_reset = datetime.now(timezone.utc)

        # Health monitoring
        self.health_checker = HealthChecker()
        self.setup_health_checks()

        # Load state from file if it exists
        self.load_state()

        self.logger.info("Crypto TGE Monitor initialized successfully")
        self.logger.info(f"Monitoring {len(COMPANIES)} companies and {len(TGE_KEYWORDS)} TGE keywords")

    def setup_logging(self):
        """Setup logging configuration and ensure log directory exists."""
        try:
            log_path = LOG_CONFIG.get('file')
            if log_path:
                os.makedirs(os.path.dirname(log_path), exist_ok=True)
        except Exception as e:
            logging.getLogger(__name__).warning(f"Failed to setup logging directory: {e}")

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

        # Additional validation
        self._validate_environment_variables()
        self._validate_file_permissions()
        
        self.logger.info("Configuration validation passed")

    def _validate_environment_variables(self):
        """Validate critical environment variables."""
        required_vars = ['EMAIL_USER', 'EMAIL_PASSWORD', 'RECIPIENT_EMAIL']
        missing_vars = []
        
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            self.logger.error(f"Missing required environment variables: {missing_vars}")
            self.logger.error("Please set these variables in your .env file or environment")
            sys.exit(1)
        
        # Validate email format
        recipient = os.getenv('RECIPIENT_EMAIL', '')
        if recipient and not self._is_valid_email(recipient):
            self.logger.error(f"Invalid recipient email format: {recipient}")
            sys.exit(1)

    def _validate_file_permissions(self):
        """Validate file permissions for logs and state."""
        try:
            # Check log directory
            log_dir = os.path.dirname(LOG_CONFIG.get('file', 'logs/crypto_monitor.log'))
            os.makedirs(log_dir, exist_ok=True)
            
            # Test write permission
            test_file = os.path.join(log_dir, '.test_write')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            
            # Check state directory
            state_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "state")
            os.makedirs(state_dir, exist_ok=True)
            
            self.logger.info("File permissions validated successfully")
        except Exception as e:
            self.logger.error(f"File permission validation failed: {str(e)}")
            sys.exit(1)

    def _is_valid_email(self, email: str) -> bool:
        """Validate email format."""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email)) and len(email) <= 254

    def setup_health_checks(self):
        """Setup health checks for system components."""
        def check_news_scraper():
            try:
                return hasattr(self.news_scraper, 'session')
            except Exception as e:
                logging.getLogger(__name__).warning(f"Health check failed for news_scraper: {e}")
                return False

        def check_twitter_monitor():
            try:
                return True  # Twitter is optional; detailed checks inside module
            except Exception as e:
                logging.getLogger(__name__).warning(f"Health check failed for twitter_monitor: {e}")
                return False

        def check_email_notifier():
            try:
                return self.email_notifier.enabled
            except Exception as e:
                logging.getLogger(__name__).warning(f"Health check failed for email_notifier: {e}")
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
        def signal_handler(signum, _frame):
            self.logger.info(f"Received signal {signum}, shutting down gracefully...")
            self.running = False
            # Don't call _graceful_shutdown here as it might cause issues in signal context
            # The main loop will handle cleanup

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Handle SIGUSR1 for status dump
        def status_handler(_signum, _frame):
            self.logger.info("Received SIGUSR1, dumping status...")
            self.print_status()
        
        try:
            signal.signal(signal.SIGUSR1, status_handler)
        except (ValueError, OSError):
            # SIGUSR1 not available on all systems
            pass

    def load_state(self):
        """Load application state from file."""
        state_file = os.path.join(STATE_DIR, 'monitor_state.json')
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
        state_file = os.path.join(STATE_DIR, 'monitor_state.json')
        try:
            state = {
                'last_run_time': self.last_run_time.isoformat() if self.last_run_time else None,
                'total_news_processed': self.total_news_processed,
                'total_tweets_processed': self.total_tweets_processed,
                'total_alerts_sent': self.total_alerts_sent,
                'last_updated': datetime.now(timezone.utc).isoformat()
            }
            with open(state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save application state: {str(e)}")

    @retry_on_failure(max_retries=1, delay=60.0, exceptions=(Exception,))
    def run_monitoring_cycle(self):
        """Run a complete monitoring cycle."""
        start_time = datetime.now(timezone.utc)
        self.cycle_count += 1

        self.logger.info(f"Starting monitoring cycle #{self.cycle_count}...")

        try:
            news_alerts: List[dict] = []
            twitter_alerts: List[dict] = []

            # ----------------------
            # News
            # ----------------------
            try:
                self.logger.info("Processing news articles...")
                # Track articles processed before processing
                articles_before = getattr(self.news_scraper, 'total_processed', 0)
                news_alerts = self.news_scraper.process_articles()
                # Calculate articles processed in this cycle
                articles_after = getattr(self.news_scraper, 'total_processed', 0)
                articles_this_cycle = articles_after - articles_before
                self.total_news_processed += articles_this_cycle
                self.logger.info(f"News processing completed: {len(news_alerts)} TGE alerts found from {articles_this_cycle} articles")
            except Exception as e:
                self.logger.error(f"Error processing news articles: {str(e)}", exc_info=True)
                self.error_count += 1

            # ----------------------
            # Twitter (hard timeout)
            # ----------------------
            try:
                if os.getenv("DISABLE_TWITTER") == "1" or not self.twitter_monitor.client:
                    self.logger.info("Twitter disabled or not configured; skipping.")
                    twitter_alerts = []
                else:
                    self.logger.info("Processing Twitter content...")
                    ok, tw_result = run_with_timeout(
                        self.twitter_monitor.process_tweets,
                        timeout=30.0,  # Reduced timeout
                        logger=self.logger
                    )
                    if ok and isinstance(tw_result, list):
                        twitter_alerts = tw_result
                        # Get actual tweets processed (not just TGE alerts)
                        tweets_this_cycle = getattr(self.twitter_monitor, 'total_processed', 0) - getattr(self, '_last_twitter_processed', 0)
                        self.total_tweets_processed += tweets_this_cycle
                        self._last_twitter_processed = getattr(self.twitter_monitor, 'total_processed', 0)
                        self.logger.info(f"Twitter processing completed: {len(twitter_alerts)} TGE alerts found from {tweets_this_cycle} tweets")
                    elif ok and tw_result is None:
                        # Timed out
                        self.logger.warning("Twitter processing timed out; continuing without Twitter results.")
                    else:
                        # Exception already logged inside run_with_timeout
                        self.logger.warning("Twitter processing failed; continuing without Twitter results.")
                        self.error_count += 1
                        twitter_alerts = []
            except Exception as e:
                # Extra belt-and-suspenders
                self.logger.error(f"Unhandled exception during Twitter processing: {e}")
                self.error_count += 1
                twitter_alerts = []

            # ----------------------
            # Filter + de-dupe + email only if NEW relevant alerts
            # ----------------------
            merged = (news_alerts or []) + (twitter_alerts or [])
            filtered_alerts, updated_seen = filter_and_dedupe(merged)

            def is_twitter(a: dict) -> bool:
                if a.get("source_type") in {"twitter", "tweet"}:
                    return True
                if a.get("channel") == "twitter":
                    return True
                if "tweet_id" in a or "user" in a or "author" in a:
                    return True
                u = (a.get("url") or "").lower()
                return "twitter.com" in u or "x.com" in u

            filtered_news    = [a for a in filtered_alerts if not is_twitter(a)]
            filtered_twitter = [a for a in filtered_alerts if is_twitter(a)]

            if filtered_news or filtered_twitter:
                self.logger.info(
                    f"Sending email alerts (filtered & deduped): "
                    f"{len(filtered_news)} news, {len(filtered_twitter)} Twitter"
                )
                try:
                    if self.email_notifier.send_tge_alert_email(filtered_news, filtered_twitter):
                        self.total_alerts_sent += 1
                        self.logger.info("Email alerts sent successfully")
                        # persist de-dup state only on successful send
                        save_seen(updated_seen)
                    else:
                        self.logger.error("Failed to send email alerts")
                        self.error_count += 1
                except Exception as e:
                    self.logger.error(f"Error sending email alerts: {str(e)}", exc_info=True)
                    self.error_count += 1
            else:
                self.logger.info("No *new* relevant TGE alerts found in this cycle")

            # Update state and reset failure counter on success
            self.last_run_time = start_time
            self.last_successful_cycle = start_time
            self.consecutive_failures = 0
            self.save_state()

            # Log cycle summary and collect metrics
            cycle_duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            self.cycle_times.append(cycle_duration)
            
            # Keep only last 100 cycle times
            if len(self.cycle_times) > 100:
                self.cycle_times = self.cycle_times[-100:]
            
            # Calculate average cycle time
            avg_cycle_time = sum(self.cycle_times) / len(self.cycle_times) if self.cycle_times else 0
            
            # Track memory usage
            try:
                import psutil
                memory_usage = psutil.Process().memory_info().rss / 1024 / 1024  # MB
                self.memory_usage.append(memory_usage)
                if len(self.memory_usage) > 100:
                    self.memory_usage = self.memory_usage[-100:]
            except ImportError:
                memory_usage = 0
            
            self.logger.info(
                f"Monitoring cycle #{self.cycle_count} completed in {cycle_duration:.2f}s "
                f"(avg: {avg_cycle_time:.2f}s) - "
                f"Found {len(news_alerts)} news alerts, {len(twitter_alerts)} Twitter alerts - "
                f"Memory: {memory_usage:.1f}MB"
            )

        except Exception as e:
            self.logger.error(f"Critical error in monitoring cycle: {str(e)}", exc_info=True)
            self.error_count += 1
            self.consecutive_failures += 1
            
            # Watchdog: if too many consecutive failures, take action
            if self.consecutive_failures >= self.max_consecutive_failures:
                self.logger.critical(f"System has failed {self.consecutive_failures} consecutive cycles. "
                                   f"Last successful cycle: {self.last_successful_cycle}")
                
                # Send critical alert email
                try:
                    self._send_critical_alert()
                except Exception as alert_error:
                    self.logger.error(f"Failed to send critical alert: {alert_error}")
                
                # Could implement restart logic here
                # For now, just log and continue
                
            # Circuit breaker reset logic
            self._reset_circuit_breakers_if_needed()
                
            raise

    def send_daily_summary(self):
        """Send daily summary email."""
        self.logger.info("Sending daily summary...")
        try:
            # Get recent alerts with error handling
            try:
                news_count = len(self.news_scraper.get_recent_tge_articles(24))
            except Exception as e:
                self.logger.warning(f"Failed to get recent news articles: {e}")
                news_count = 0
                
            try:
                twitter_count = len(self.twitter_monitor.get_recent_tge_tweets(24))
            except Exception as e:
                self.logger.warning(f"Failed to get recent tweets: {e}")
                twitter_count = 0
            
            # Send summary
            success = self.email_notifier.send_daily_summary(
                news_count=news_count,
                twitter_count=twitter_count,
                total_processed=self.total_news_processed + self.total_tweets_processed
            )
            
            if success:
                self.logger.info("Daily summary sent successfully")
            else:
                self.logger.error("Failed to send daily summary email")
                
        except Exception as e:
            self.logger.error(f"Failed to send daily summary: {str(e)}", exc_info=True)

    def setup_schedule(self):
        """Setup the monitoring schedule."""
        schedule.every().day.at("09:00").do(self.run_monitoring_cycle)  # run once daily at 9 AM UTC
        # Schedule daily summary at 9:00 AM PST (17:00 UTC)
        schedule.every().day.at("17:00").do(self.send_daily_summary)
        self.logger.info("Schedule configured:")
        self.logger.info("- Monitoring cycle: Once daily at 9:00 AM UTC")
        self.logger.info("- Daily summary: 9:00 AM PST (17:00 UTC)")

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
        try:
            self.run_monitoring_cycle()
        except Exception as e:
            self.logger.error(f"Initial cycle failed: {str(e)}", exc_info=True)

        # Main loop
        while self.running:
            try:
                schedule.run_pending()
                
                # Periodic health check
                if self.cycle_count % 10 == 0:  # Every 10 cycles
                    self._perform_health_check()
                
                time.sleep(60)  # Check every minute
            except KeyboardInterrupt:
                self.logger.info("Received keyboard interrupt, shutting down...")
                break
            except Exception as e:
                self.logger.error(f"Error in main loop: {str(e)}", exc_info=True)
                self.error_count += 1
                time.sleep(60)  # Wait before retrying

        # Graceful shutdown
        self._graceful_shutdown()

    def _graceful_shutdown(self):
        """Perform graceful shutdown with cleanup."""
        self.logger.info("Performing graceful shutdown...")
        self.running = False
        
        try:
            # Save final state
            self.save_state()
            self.logger.info("Final state saved")
        except Exception as e:
            self.logger.error(f"Error saving final state: {str(e)}")
        
        try:
            # Close any open connections
            if hasattr(self.news_scraper, 'session') and self.news_scraper.session:
                self.news_scraper.session.close()
        except Exception as e:
            self.logger.error(f"Error closing news scraper session: {str(e)}")
        
        self.logger.info("Graceful shutdown completed")

    def _reset_circuit_breakers_if_needed(self):
        """Reset circuit breakers if enough time has passed."""
        now = datetime.now(timezone.utc)
        time_since_reset = (now - self.last_circuit_breaker_reset).total_seconds()
        
        if time_since_reset >= self.circuit_breaker_reset_time:
            self.logger.info("Resetting circuit breakers...")
            
            # Reset news scraper circuit breakers
            if hasattr(self.news_scraper, '_failed_feeds'):
                failed_count = len(self.news_scraper._failed_feeds)
                if failed_count > 0:
                    self.news_scraper._failed_feeds.clear()
                    self.news_scraper._feed_failure_count.clear()
                    self.logger.info(f"Reset {failed_count} failed news feeds")
            
            # Reset Twitter circuit breakers
            if hasattr(self.twitter_monitor, '_since'):
                # Clear old since_ids to force fresh data
                old_count = len(self.twitter_monitor._since)
                self.twitter_monitor._since.clear()
                self.logger.info(f"Reset {old_count} Twitter since_ids")
            
            self.last_circuit_breaker_reset = now
            self.logger.info("Circuit breakers reset completed")

    def _perform_health_check(self):
        """Perform comprehensive health check."""
        try:
            health_results = self.health_checker.run_checks()
            
            # Log health status
            for component, result in health_results.items():
                if result['status'] == 'error':
                    self.logger.error(f"Health check failed for {component}: {result.get('error', 'Unknown error')}")
                elif result['status'] == 'unhealthy':
                    self.logger.warning(f"Health check unhealthy for {component}")
                else:
                    self.logger.debug(f"Health check healthy for {component}")
            
            # Check for critical issues
            error_components = [comp for comp, result in health_results.items() if result['status'] == 'error']
            if error_components:
                self.logger.warning(f"Critical health issues detected: {error_components}")
                
        except Exception as e:
            self.logger.error(f"Health check failed: {str(e)}", exc_info=True)

    def _send_critical_alert(self):
        """Send critical system alert email."""
        try:
            subject = "🚨 CRITICAL: TGE Monitor System Failure"
            html = f"""
            <!DOCTYPE html>
            <html>
            <head><meta charset="UTF-8"></head>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width:600px;margin:0 auto;padding:20px;">
                    <h2 style="color: #dc3545;">🚨 CRITICAL SYSTEM ALERT</h2>
                    <p><strong>TGE Monitor System has failed {self.consecutive_failures} consecutive cycles.</strong></p>
                    <ul>
                        <li><strong>Last successful cycle:</strong> {self.last_successful_cycle or 'Never'}</li>
                        <li><strong>Total errors:</strong> {self.error_count}</li>
                        <li><strong>System uptime:</strong> {datetime.now(timezone.utc) - self.start_time if hasattr(self, 'start_time') else 'Unknown'}</li>
                        <li><strong>Current time:</strong> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</li>
                    </ul>
                    <p style="color: #dc3545;"><strong>Immediate attention required!</strong></p>
                </div>
            </body>
            </html>
            """
            
            self.email_notifier._send_email(subject, html)
            self.logger.info("Critical alert email sent")
            
        except Exception as e:
            self.logger.error(f"Failed to send critical alert email: {str(e)}")

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
        if os.getenv("DISABLE_TWITTER") == "1" or not self.twitter_monitor.client:
            self.logger.info("Twitter monitor disabled; skipping test")
        else:
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
        """Get current system status with enhanced metrics."""
        health_status = self.health_checker.get_overall_status()
        news_stats = self.news_scraper.get_stats()
        twitter_stats = self.twitter_monitor.get_stats()

        # Calculate enhanced metrics
        uptime = datetime.now(timezone.utc) - self.start_time if hasattr(self, 'start_time') else None
        avg_cycle_time = sum(self.cycle_times) / len(self.cycle_times) if self.cycle_times else 0
        max_cycle_time = max(self.cycle_times) if self.cycle_times else 0
        min_cycle_time = min(self.cycle_times) if self.cycle_times else 0
        
        # Memory metrics
        current_memory = self.memory_usage[-1] if self.memory_usage else 0
        avg_memory = sum(self.memory_usage) / len(self.memory_usage) if self.memory_usage else 0
        max_memory = max(self.memory_usage) if self.memory_usage else 0

        status = {
            'running': self.running,
            'last_run_time': self.last_run_time.isoformat() if self.last_run_time else None,
            'cycle_count': self.cycle_count,
            'error_count': self.error_count,
            'error_rate': (self.error_count / self.cycle_count * 100) if self.cycle_count > 0 else 0,
            'health_status': health_status,
            'total_news_processed': self.total_news_processed,
            'total_tweets_processed': self.total_tweets_processed,
            'total_alerts_sent': self.total_alerts_sent,
            'companies_monitored': len(COMPANIES),
            'tge_keywords': len(TGE_KEYWORDS),
            'email_enabled': self.email_notifier.enabled,
            'twitter_enabled': self.twitter_monitor.client is not None if hasattr(self.twitter_monitor, "client") else True,
            'news_stats': news_stats,
            'twitter_stats': twitter_stats,
            'uptime': str(uptime) if uptime else None,
            'uptime_seconds': uptime.total_seconds() if uptime else 0,
            'performance': {
                'avg_cycle_time': round(avg_cycle_time, 2),
                'max_cycle_time': round(max_cycle_time, 2),
                'min_cycle_time': round(min_cycle_time, 2),
                'current_memory_mb': round(current_memory, 1),
                'avg_memory_mb': round(avg_memory, 1),
                'max_memory_mb': round(max_memory, 1)
            },
            'feed_health': {
                'failed_feeds': len(getattr(self.news_scraper, '_failed_feeds', set())),
                'total_feeds': len(NEWS_SOURCES)
            }
        }
        return status

    def print_status(self):
        """Print current system status."""
        status = self.get_status()
        print("\n" + "=" * 60)
        print("🚀 CRYPTO TGE MONITOR STATUS")
        print("=" * 60)
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

        print("\n📊 COMPONENT STATISTICS:")
        print(f"News - Processed: {status['news_stats']['total_processed']}, TGE: {status['news_stats']['total_tge_articles']}")
        print(f"Twitter - Processed: {status['twitter_stats']['total_processed']}, TGE: {status['twitter_stats']['total_tge_tweets']}")
        print("=" * 60 + "\n")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Crypto TGE Monitor')
    parser.add_argument('--mode', choices=['once', 'continuous', 'test', 'status'],
                        default='continuous', help='Run mode')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable verbose logging')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

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

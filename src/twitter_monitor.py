"""
Twitter Monitoring Module for Crypto TGE Events

This module handles Twitter API integration to monitor crypto-related accounts
for TGE announcements and relevant news.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Set, Optional
import time

import tweepy
from tweepy.errors import TooManyRequests, Forbidden

from config import TWITTER_CONFIG, TWITTER_ACCOUNTS, COMPANIES, TGE_KEYWORDS
from utils import (
    retry_on_failure, generate_content_hash, is_content_duplicate,
    sanitize_text, calculate_relevance_score, is_recent_content,
    save_json_file, load_json_file, truncate_text
)


def _to_aware_utc(dt):
    """Coerce datetime to tz-aware UTC (handles naive datetimes)."""
    if dt is None:
        return None
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    return dt


class TwitterMonitor:
    """Class for monitoring Twitter accounts for TGE-related content."""

    def __init__(self, state_file: str = 'logs/twitter_monitor_state.json'):
        self.setup_logging()
        self.api = None  # v1.1 not used
        self.client: Optional[tweepy.Client] = None  # v2 client
        self.processed_tweets: Set[str] = set()
        self.tge_tweets: List[Dict] = []
        self.seen_content_hashes: Set[str] = set()
        self.state_file = state_file
        self.rate_limited = False
        self._last_warnings = {"rate_limited": False, "forbidden": False, "disabled": False}

        # Load persistent state
        self.load_state()

        self._setup_twitter_api()
        self.logger.info("TwitterMonitor initialized successfully")

    def setup_logging(self):
        """Setup logging configuration."""
        self.logger = logging.getLogger("twitter_monitor")

    def load_state(self):
        """Load persistent state from file."""
        state = load_json_file(self.state_file, {})
        if state:
            self.processed_tweets = set(state.get('processed_tweets', []))
            self.seen_content_hashes = set(state.get('seen_content_hashes', []))
            self.tge_tweets = state.get('tge_tweets', [])
            self.logger.info(
                f"Loaded state: {len(self.processed_tweets)} processed tweets, {len(self.tge_tweets)} TGE tweets"
            )

    def save_state(self):
        """Save persistent state to file."""
        state = {
            'processed_tweets': list(self.processed_tweets),
            'seen_content_hashes': list(self.seen_content_hashes),
            'tge_tweets': self.tge_tweets,
            'last_updated': datetime.now(timezone.utc).isoformat()
        }
        if save_json_file(self.state_file, state):
            self.logger.debug("State saved successfully")
        else:
            self.logger.warning("Failed to save state")

    def _setup_twitter_api(self):
        """Initialize Twitter API v2 client (v1.1 timeline is not available on most tiers)."""
        try:
            self.api = None  # don't use v1.1
            if TWITTER_CONFIG.get('bearer_token'):
                # Non-blocking on rate limits: we handle TooManyRequests ourselves
                self.client = tweepy.Client(
                    bearer_token=TWITTER_CONFIG['bearer_token'],
                    wait_on_rate_limit=False
                )
                self.logger.info("Twitter v2 client initialized")
            else:
                self.client = None
                self._last_warnings["disabled"] = True
                self.logger.warning("No bearer_token configured; Twitter monitoring disabled.")
        except Exception as e:
            self.logger.error(f"Failed to initialize Twitter client: {e}", exc_info=True)
            self.api = None
            self.client = None
            self._last_warnings["disabled"] = True

    # Do not retry TooManyRequests here (that would block/sleep)
    @retry_on_failure(max_retries=2, delay=3.0, exceptions=(tweepy.TwitterServerError,))
    def fetch_user_tweets(self, username: str, count: int = 50) -> List[Dict]:
        """
        Fetch recent tweets from a specific user via v2 recent search:
        uses `from:username -is:retweet -is:reply lang:en`.
        Non-blocking on rate limits (returns partial/empty and continues).
        """
        if not self.client:
            self.logger.warning("Twitter Client v2 not available")
            self._last_warnings["disabled"] = True
            return []

        try:
            username = username.lstrip('@')
            query = f'from:{username} -is:retweet -is:reply lang:en'
            resp = self.client.search_recent_tweets(
                query=query,
                max_results=min(count, 100),
                tweet_fields=['created_at', 'public_metrics', 'author_id'],
                user_fields=['username', 'name', 'public_metrics'],
                expansions=['author_id'],
            )
            if not resp or not resp.data:
                self.logger.info(f"No recent tweets found for @{username}")
                return []

            users = {u.id: u for u in (resp.includes.get('users') or [])}
            out: List[Dict] = []
            for t in resp.data:
                u = users.get(t.author_id)
                out.append({
                    'id': str(t.id),
                    'text': sanitize_text(t.text),
                    'created_at': _to_aware_utc(t.created_at),  # ensure aware UTC
                    'user': {
                        'screen_name': (u.username if u else username),
                        'name': (u.name if u else username),
                        'followers_count': (u.public_metrics or {}).get('followers_count', 0) if u else 0,
                    },
                    'retweet_count': (t.public_metrics or {}).get('retweet_count', 0),
                    'favorite_count': (t.public_metrics or {}).get('like_count', 0),
                    'url': f"https://twitter.com/{(u.username if u else username)}/status/{t.id}",
                })

            self.logger.info(f"Fetched {len(out)} tweets from @{username} (v2 search)")
            return out

        except TooManyRequests as e:
            self.logger.warning(f"Rate limit exceeded for @{username}; continuing without waiting. {e}")
            self.rate_limited = True
            self._last_warnings["rate_limited"] = True
            return []
        except Forbidden as e:
            # Some accounts or queries are not allowed on certain tiers
            self.logger.warning(f"Forbidden fetching @{username} (v2 search): {e}")
            self._last_warnings["forbidden"] = True
            return []
        except Exception as e:
            self.logger.error(f"Error fetching tweets from @{username}: {e}", exc_info=True)
            return []

    def search_tweets(self, query: str, count: int = 100) -> List[Dict]:
        """Search for tweets using Twitter API v2 (non-blocking on RL)."""
        if not self.client:
            self.logger.warning("Twitter Client v2 not available")
            self._last_warnings["disabled"] = True
            return []

        try:
            resp = self.client.search_recent_tweets(
                query=query,
                max_results=min(count, 100),
                tweet_fields=['created_at', 'public_metrics', 'author_id'],
                user_fields=['username', 'name', 'public_metrics'],
                expansions=['author_id'],
            )
            if not resp or not resp.data:
                return []

            users = {u.id: u for u in (resp.includes.get('users') or [])}
            processed_tweets: List[Dict] = []
            for t in resp.data:
                u = users.get(t.author_id)
                processed_tweets.append({
                    'id': str(t.id),
                    'text': sanitize_text(t.text),
                    'created_at': _to_aware_utc(t.created_at),  # ensure aware UTC
                    'user': {
                        'screen_name': (u.username if u else 'unknown'),
                        'name': (u.name if u else 'unknown'),
                        'followers_count': (u.public_metrics or {}).get('followers_count', 0) if u else 0,
                    },
                    'retweet_count': (t.public_metrics or {}).get('retweet_count', 0),
                    'favorite_count': (t.public_metrics or {}).get('like_count', 0),
                    'url': f"https://twitter.com/{(u.username if u else 'unknown')}/status/{t.id}",
                })
            self.logger.info(f"Found {len(processed_tweets)} tweets for query: {query}")
            return processed_tweets

        except TooManyRequests as e:
            self.logger.warning(f"Rate limit exceeded during search; continuing without waiting. {e}")
            self.rate_limited = True
            self._last_warnings["rate_limited"] = True
            return []
        except Forbidden as e:
            self.logger.warning(f"Forbidden search query '{query}': {e}")
            self._last_warnings["forbidden"] = True
            return []
        except Exception as e:
            self.logger.error(f"Error searching tweets for query '{query}': {e}", exc_info=True)
            return []

    def monitor_accounts(self) -> List[Dict]:
        """Monitor all configured Twitter accounts for TGE-related content."""
        all_tweets: List[Dict] = []
        for account in TWITTER_ACCOUNTS:
            try:
                tweets = self.fetch_user_tweets(account, count=20)
                if tweets:
                    all_tweets.extend(tweets)
                # tiny pacing; set to 0 for max speed
                time.sleep(0.2)
            except Exception as e:
                self.logger.error(f"Error monitoring account {account}: {e}", exc_info=True)
                continue
        return all_tweets

    def search_tge_keywords(self) -> List[Dict]:
        """Search for tweets containing TGE-related keywords."""
        all_tweets: List[Dict] = []
        search_queries: List[str] = []

        # Companies x limited keywords to keep calls bounded
        for company in COMPANIES[:10]:
            for keyword in TGE_KEYWORDS[:5]:
                query = f'"{company}" {keyword} -is:retweet lang:en'
                search_queries.append(query)

        # General TGE terms
        general_queries = [
            'TGE token generation event -is:retweet lang:en',
            'crypto token launch -is:retweet lang:en',
            'airdrop announcement -is:retweet lang:en',
            'token sale ICO IDO -is:retweet lang:en',
        ]
        search_queries.extend(general_queries)

        for query in search_queries:
            try:
                tweets = self.search_tweets(query, count=20)
                if tweets:
                    all_tweets.extend(tweets)
                time.sleep(0.2)
            except Exception as e:
                self.logger.error(f"Error searching with query '{query}': {e}", exc_info=True)
                continue

        return all_tweets

    def analyze_tweet_for_tge(self, tweet: Dict) -> Dict:
        """Analyze a tweet for TGE-related content."""
        text = tweet['text']

        # Dedup by content
        if is_content_duplicate(text, self.seen_content_hashes):
            self.logger.debug(f"Duplicate content detected for tweet: {tweet['id']}")
            return {
                'tweet': tweet,
                'mentioned_companies': [],
                'found_keywords': [],
                'relevance_score': 0.0,
                'is_tge_related': False,
                'analysis_timestamp': datetime.now(timezone.utc),
                'is_duplicate': True,
            }

        text_lower = text.lower()
        mentioned_companies = [c for c in COMPANIES if c.lower() in text_lower]
        found_keywords = [k for k in TGE_KEYWORDS if k.lower() in text_lower]

        keyword_weights = {
            'tge': 0.5,
            'token generation event': 0.5,
            'token launch': 0.4,
            'airdrop': 0.3,
            'token sale': 0.25,
            'ico': 0.25,
            'ido': 0.25,
            'token listing': 0.2,
            'token distribution': 0.2,
        }

        relevance_score = calculate_relevance_score(
            mentioned_companies, found_keywords, text,
            keyword_weights=keyword_weights,
            company_weight=0.4,
        )

        # Engagement boost
        engagement_score = (
            tweet.get('retweet_count', 0) * 0.001 +
            tweet.get('favorite_count', 0) * 0.0005
        )
        relevance_score = min(relevance_score + min(engagement_score, 0.2), 1.0)

        # Follower boost
        followers = tweet.get('user', {}).get('followers_count', 0)
        if followers > 100000:
            relevance_score += 0.1
        elif followers > 10000:
            relevance_score += 0.05
        relevance_score = min(relevance_score, 1.0)

        is_tge_related = (
            len(mentioned_companies) > 0 and
            len(found_keywords) > 0 and
            relevance_score > 0.3
        )

        return {
            'tweet': tweet,
            'mentioned_companies': mentioned_companies,
            'found_keywords': found_keywords,
            'relevance_score': relevance_score,
            'is_tge_related': is_tge_related,
            'analysis_timestamp': datetime.now(timezone.utc),
            'is_duplicate': False,
        }

    def process_tweets(self) -> List[Dict]:
        """Process all fetched tweets and identify TGE-related content."""
        self.rate_limited = False
        self._last_warnings = {"rate_limited": False, "forbidden": False, "disabled": False}

        # Tweets from monitored accounts (non-blocking on RL)
        account_tweets = self.monitor_accounts()

        # Tweets from keyword searches (non-blocking on RL)
        search_tweets = self.search_tge_keywords()

        # Combine and deduplicate
        all_tweets = account_tweets + search_tweets
        unique_tweets = {tweet['id']: tweet for tweet in all_tweets}.values()

        tge_tweets: List[Dict] = []
        for tweet in unique_tweets:
            if tweet['id'] in self.processed_tweets:
                continue
            self.processed_tweets.add(tweet['id'])

            # Only process recent tweets (last 24 hours) — coerce to aware UTC first
            created = _to_aware_utc(tweet.get('created_at'))
            if not is_recent_content(created, hours=24):
                continue

            analysis = self.analyze_tweet_for_tge(tweet)
            if analysis['is_tge_related'] and not analysis.get('is_duplicate', False):
                tge_tweets.append(analysis)
                self.logger.info(
                    f"TGE-related tweet found: @{tweet['user']['screen_name']} - "
                    f"{truncate_text(tweet['text'], 100)}... "
                    f"(Companies: {analysis['mentioned_companies']}, "
                    f"Score: {analysis['relevance_score']:.2f})"
                )

        self.tge_tweets.extend(tge_tweets)
        self.save_state()

        if self.rate_limited:
            self.logger.warning("Twitter was rate-limited during this cycle; returning partial results.")

        return tge_tweets

    def get_recent_tge_tweets(self, hours: int = 24) -> List[Dict]:
        """Get TGE tweets from the last N hours."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        return [
            tweet for tweet in self.tge_tweets
            if tweet['tweet'].get('created_at') and _to_aware_utc(tweet['tweet']['created_at']) > cutoff_time
        ]

    def format_tweet_alert(self, analysis: Dict) -> str:
        """Format TGE tweet analysis into a readable alert."""
        tweet = analysis['tweet']
        ts = _to_aware_utc(tweet.get('created_at'))
        ts_str = ts.strftime('%Y-%m-%d %H:%M UTC') if isinstance(ts, datetime) else str(ts)

        alert = f"""
🐦 TGE TWEET ALERT - @{tweet['user']['screen_name']}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

👤 User: {tweet['user']['name']} (@{tweet['user']['screen_name']})
👥 Followers: {tweet['user']['followers_count']:,}
📅 Posted: {ts_str}
🔗 Link: {tweet['url']}

📊 Engagement: {tweet['retweet_count']} RTs, {tweet['favorite_count']} Likes

🏢 Companies Mentioned: {', '.join(analysis['mentioned_companies']) if analysis['mentioned_companies'] else 'None'}
🔑 TGE Keywords: {', '.join(analysis['found_keywords']) if analysis['found_keywords'] else 'None'}
📊 Relevance Score: {analysis['relevance_score']:.2f}/1.0

💬 Tweet:
{tweet['text']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        """
        return alert.strip()

    def get_stats(self) -> Dict[str, int]:
        """Get statistics about processed tweets."""
        return {
            'total_processed': len(self.processed_tweets),
            'total_tge_tweets': len(self.tge_tweets),
            'recent_tge_tweets': len(self.get_recent_tge_tweets(24)),
            'unique_content_hashes': len(self.seen_content_hashes),
        }


if __name__ == "__main__":
    monitor = TwitterMonitor()
    tge_tweets = monitor.process_tweets()

    print(f"Found {len(tge_tweets)} TGE-related tweets")
    for analysis in tge_tweets:
        print(monitor.format_tweet_alert(analysis))
        print("\n" + "="*50 + "\n")

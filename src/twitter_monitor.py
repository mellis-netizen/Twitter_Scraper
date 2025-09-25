import os
import re
import json
import time
import logging
from typing import List, Dict, Optional
from datetime import datetime
from urllib.parse import quote_plus

import tweepy
from tweepy.errors import TooManyRequests, HTTPException

from config import COMPANIES, TGE_KEYWORDS, HIGH_CONFIDENCE_TGE_KEYWORDS, MEDIUM_CONFIDENCE_TGE_KEYWORDS

# ------------------ persistent since_id per user/search ------------------

STATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "state")
SINCE_PATH = os.path.join(STATE_DIR, "twitter_since.json")


def _load_since_map() -> dict:
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        if os.path.isfile(SINCE_PATH):
            with open(SINCE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logging.getLogger(__name__).warning(f"Failed to load Twitter since map: {e}")
    return {}


def _save_since_map(since_map: dict) -> None:
    os.makedirs(STATE_DIR, exist_ok=True)
    tmp = SINCE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(since_map, f, ensure_ascii=False, indent=2)
    os.replace(tmp, SINCE_PATH)


# ------------------ helpers ------------------

def _has_token(text: str, token: str) -> bool:
    token = token.strip()
    if not token:
        return False
    return re.search(rf"\b{re.escape(token)}\b", text, flags=re.IGNORECASE) is not None


def _matches_company_and_keyword(text: str) -> bool:
    """
    Enhanced Twitter matching logic - same as main.py but adapted for tweets
    """
    if not text or len(text.strip()) < 10:
        return False

    text = text.lower()

    def _has(token: str) -> bool:
        """Check if token exists as whole word"""
        if not token.strip():
            return False
        token = re.escape(token.strip())
        return re.search(rf"\b{token}\b", text, flags=re.IGNORECASE) is not None

    def _find_company_matches() -> list:
        """Find all matching companies and return match details"""
        matches = []
        for c in COMPANIES:
            if not isinstance(c, dict):
                continue

            company_name = c.get("name", "")
            aliases = c.get("aliases", [])
            tokens = c.get("tokens", [])
            exclusions = c.get("exclusions", [])

            # Check for exclusion words first
            if any(_has(excl) for excl in exclusions):
                continue

            # Check company name and aliases
            all_names = [company_name] + aliases
            name_match = any(_has(name) for name in all_names if name)

            # Check token symbols
            token_match = any(_has(token) for token in tokens)

            if name_match or token_match:
                matches.append({
                    'company': c,
                    'name_match': name_match,
                    'token_match': token_match
                })
        return matches

    def _has_high_confidence_keywords() -> list:
        """Find high confidence TGE keywords"""
        return [k for k in HIGH_CONFIDENCE_TGE_KEYWORDS if _has(k)]

    def _has_medium_confidence_keywords() -> list:
        """Find medium confidence TGE keywords"""
        return [k for k in MEDIUM_CONFIDENCE_TGE_KEYWORDS if _has(k)]

    def _has_multiple_tge_signals() -> bool:
        """Check for multiple TGE-related signals in the text"""
        tge_signals = [
            "token", "coin", "crypto", "blockchain", "defi", "web3",
            "mainnet", "testnet", "protocol", "network", "chain",
            "launch", "release", "deploy", "announce", "live"
        ]
        signal_count = sum(1 for signal in tge_signals if _has(signal))
        return signal_count >= 2  # Lower threshold for tweets (shorter content)

    # Find company matches
    company_matches = _find_company_matches()
    if not company_matches:
        return False

    # Strategy 1: High confidence TGE keywords + company match
    high_conf_keywords = _has_high_confidence_keywords()
    if high_conf_keywords and company_matches:
        # Priority-based validation for Twitter (more restrictive due to noise)
        for match in company_matches:
            priority = match['company'].get('priority', 'LOW')
            if priority == 'HIGH':
                return True  # High priority companies with high confidence keywords
            elif priority == 'MEDIUM' and len(high_conf_keywords) >= 1:
                return True  # Medium priority needs strong keyword
        return False  # Twitter requires priority companies

    # Strategy 2: Medium confidence keywords + company + multiple TGE signals (HIGH only)
    medium_conf_keywords = _has_medium_confidence_keywords()
    if medium_conf_keywords and company_matches and _has_multiple_tge_signals():
        for match in company_matches:
            if match['company'].get('priority') == 'HIGH':
                return True
        return False

    # Strategy 3: Token symbol + specific TGE action words (HIGH priority only)
    token_specific_actions = ["launch", "release", "deploy", "mint", "distribute", "airdrop"]
    for match in company_matches:
        if (match['token_match'] and
            any(_has(action) for action in token_specific_actions) and
            match['company'].get('priority') == 'HIGH'):
            return True

    return False


def _call_with_backoff(fn, *args, **kwargs):
    delay = 1  # Start with shorter delay
    max_retries = 3  # Reduced retries
    for attempt in range(max_retries):
        try:
            return fn(*args, **kwargs)
        except TooManyRequests:
            if attempt < max_retries - 1:
                time.sleep(min(delay, 30))  # Cap delay at 30 seconds
                delay = min(delay * 2, 30)
            else:
                raise
        except HTTPException as e:
            if attempt < max_retries - 1:
                time.sleep(min(delay, 15))  # Cap delay at 15 seconds
                delay = min(delay * 2, 15)
            else:
                raise
        except Exception as e:
            # For other exceptions, don't retry
            raise
    raise RuntimeError("Twitter API retries exhausted")


# ------------------ monitor class ------------------

class TwitterMonitor:
    """
    Twitter monitor that:
    - pulls user timelines incrementally using since_id
    - optionally runs combined (company AND keyword) searches
    - returns a list of alert dicts expected by main/email
    """

    def __init__(self):
        self.logger = logging.getLogger("twitter_monitor")
        
        # Initialize stats tracking
        self.total_processed = 0
        self.total_tge_tweets = 0
        self._recent_tweets = []  # Cache for recent tweets

        bearer = os.getenv("TWITTER_BEARER_TOKEN")
        if not bearer:
            self.logger.warning("TWITTER_BEARER_TOKEN missing; Twitter monitoring disabled")
            self.client = None
            self.api = None
            self._since = {}
            self.accounts: list[str] = []
            self.search_enabled = False
            return
        
        # Validate bearer token format
        if not self._validate_bearer_token(bearer):
            self.logger.error("Invalid TWITTER_BEARER_TOKEN format; Twitter monitoring disabled")
            self.client = None
            self.api = None
            self._since = {}
            self.accounts: list[str] = []
            self.search_enabled = False
            return

        self.client = tweepy.Client(bearer_token=bearer, wait_on_rate_limit=False)
        self.api = self.client  # maintain attribute used elsewhere

        # Accounts: use config-defined accounts or env comma list
        from config import TWITTER_ACCOUNTS
        env_users = os.getenv("TWITTER_USERS", "").strip()
        if env_users:
            self.accounts = [u.strip().lstrip("@") for u in env_users.split(",") if u.strip()]
        else:
            # Use accounts from config, removing @ symbols
            self.accounts = [acc.lstrip("@") for acc in TWITTER_ACCOUNTS if acc]

        # Toggle search if desired (default on)
        self.search_enabled = os.getenv("TWITTER_ENABLE_SEARCH", "1") not in {"0", "false", "False"}

        self._since = _load_since_map()

    # -------- public API expected by main.py --------

    def process_tweets(self) -> List[Dict]:
        if not self.client:
            self.logger.warning("Twitter client not available; skipping Twitter processing")
            return []

        out: list[dict] = []

        # 1) timelines
        if self.accounts:
            for handle in self.accounts[:5]:  # Limit to first 5 accounts to prevent hanging
                try:
                    u = _call_with_backoff(self.client.get_user, username=handle, user_fields=["id"])
                except Exception as e:
                    self.logger.warning(f"get_user({handle}) failed: {e}")
                    continue
                user = (u.data or None)
                if not user:
                    continue
                uid = str(user.id)
                try:
                    timeline_results = self._fetch_user_timeline(uid, handle)
                    out.extend(timeline_results)
                except Exception as e:
                    self.logger.warning(f"Failed to fetch timeline for {handle}: {e}")
                    continue
                time.sleep(0.2)  # Reduced sleep time

        # 2) combined queries (company AND keyword)
        if self.search_enabled:
            try:
                search_results = self._search_company_keyword_batches()
                out.extend(search_results)
            except Exception as e:
                self.logger.warning(f"Twitter search failed: {e}")
        
        # annotate as twitter and shape minimal fields downstream expects
        for a in out:
            a.setdefault("source", "Twitter")
            a.setdefault("source_type", "twitter")

        # Update stats
        self.total_processed += len(out)
        self.total_tge_tweets += len(out)
        
        # Cache recent tweets for daily summary
        self._recent_tweets.extend(out)
        # Keep only last 100 tweets to avoid memory issues
        self._recent_tweets = self._recent_tweets[-100:]

        # stats
        self.logger.info(f"process_tweets: produced {len(out)} candidate alerts")
        return out

    def _validate_bearer_token(self, token: str) -> bool:
        """Validate Twitter bearer token format."""
        if not token or not isinstance(token, str):
            return False
        
        # Remove "Bearer " prefix if present for validation
        clean_token = token.replace('Bearer ', '') if token.startswith('Bearer ') else token
        
        # Basic format validation - Twitter bearer tokens are typically 40+ characters
        if len(clean_token) < 40:
            return False
        
        # Check for common invalid patterns
        invalid_patterns = ['your_bearer_token', 'placeholder', 'test', 'example', 'test_bearer_token']
        if any(pattern in clean_token.lower() for pattern in invalid_patterns):
            return False
        
        return True

    def get_recent_tge_tweets(self, hours: int = 24) -> List[Dict]:
        """Return TGE tweets from the last N hours."""
        if not self._recent_tweets:
            return []
        
        from datetime import datetime, timezone, timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        recent = []
        for tweet in self._recent_tweets:
            try:
                # Parse published time
                published = tweet.get("published")
                if isinstance(published, str):
                    published = datetime.fromisoformat(published.replace('Z', '+00:00'))
                elif not isinstance(published, datetime):
                    continue
                    
                if published >= cutoff:
                    recent.append(tweet)
            except Exception as e:
                logging.getLogger(__name__).warning(f"Error processing tweet timestamp: {e}")
                continue
                
        return recent

    def get_stats(self) -> Dict:
        return {
            "total_processed": self.total_processed,
            "total_tge_tweets": self.total_tge_tweets
        }

    # -------- internals --------

    def _fetch_user_timeline(self, user_id: str, handle: str, max_results: int = 25) -> List[Dict]:
        alerts: list[dict] = []
        since_id = self._since.get(f"user:{user_id}")
        try:
            resp = _call_with_backoff(
                self.client.get_users_tweets,
                id=user_id,
                since_id=since_id,
                exclude=["retweets", "replies"],
                max_results=max_results,
                tweet_fields=["created_at", "text", "lang"]
            )
        except Exception as e:
            self.logger.warning(f"fetch timeline @{handle} failed: {e}")
            return alerts

        newest = since_id
        data = resp.data or []
        for t in data:
            try:
                # Validate tweet object
                if not hasattr(t, 'id') or not hasattr(t, 'text'):
                    continue
                    
                # Extract and validate text
                txt = getattr(t, 'text', '') or ""
                if not isinstance(txt, str):
                    txt = str(txt) if txt else ""
                txt = txt.strip()[:280]  # Limit to tweet length
                
                if not txt or not _matches_company_and_keyword(txt):
                    continue
                
                # Validate tweet ID
                tweet_id = str(getattr(t, 'id', ''))
                if not tweet_id or not tweet_id.isdigit():
                    continue
                
                # Validate handle
                if not handle or not isinstance(handle, str):
                    continue
                handle = handle.strip().lstrip('@')[:50]  # Limit handle length
                
                # Create URL safely
                url = f"https://x.com/{handle}/status/{tweet_id}"
                
                # Parse created_at safely
                published = None
                created_at = getattr(t, 'created_at', None)
                if created_at:
                    try:
                        if hasattr(created_at, 'isoformat'):
                            published = created_at.isoformat()
                        else:
                            published = str(created_at)
                    except Exception:
                        published = None
                
                alerts.append({
                    "title": f"@{handle}: possible TGE signal",
                    "text": txt,
                    "url": url,
                    "published": published,
                    "author": handle,
                    "tweet_id": tweet_id,
                    "channel": "twitter",
                })
                
                # Update newest ID safely
                try:
                    if newest is None or int(tweet_id) > int(newest or 0):
                        newest = tweet_id
                except (ValueError, TypeError):
                    pass
                    
            except Exception as e:
                self.logger.warning(f"Error processing tweet from @{handle}: {e}")
                continue

        if newest is not None:
            self._since[f"user:{user_id}"] = str(newest)
            _save_since_map(self._since)
        return alerts

    def _search_company_keyword_batches(self, per_query_limit: int = 25) -> List[Dict]:
        """
        Build queries like:
          ("offchain labs" OR "arbitrum") ("token" OR "tge" OR "airdrop") lang:en -is:retweet
        and page through a few until rate-limit is hit (backoff handles retries).
        Track a simple since_id per query key.
        """
        alerts: list[dict] = []

        # Build alias buckets for companies
        company_buckets: list[list[str]] = []
        for c in COMPANIES:
            if isinstance(c, dict):
                names = [c.get("name", "")] + (c.get("aliases", []) or [])
            else:
                names = [str(c)]
            names = [n.strip() for n in names if n and n.strip()]
            if names:
                company_buckets.append(names)

        if not company_buckets or not TGE_KEYWORDS:
            return alerts

        kw_clause = "(" + " OR ".join(f'"{k}"' if " " in k else k for k in TGE_KEYWORDS) + ")"
        for names in company_buckets:
            comp_clause = "(" + " OR ".join(f'"{n}"' if " " in n else n for n in names) + ")"
            q = f"{comp_clause} {kw_clause} lang:en -is:retweet"

            key = f"q:{comp_clause}|{kw_clause}"
            since_id = self._since.get(key)

            try:
                resp = _call_with_backoff(
                    self.client.search_recent_tweets,
                    query=q,
                    since_id=since_id,
                    max_results=min(100, per_query_limit),
                    tweet_fields=["created_at", "text", "lang"],
                )
            except TooManyRequests:
                self.logger.warning("Rate limited during search; continuing with backoff")
                continue
            except Exception as e:
                self.logger.warning(f"search_recent_tweets failed: {e}")
                continue

            newest = since_id
            for t in resp.data or []:
                txt = t.text or ""
                if not _matches_company_and_keyword(txt):
                    continue
                url = f"https://x.com/i/web/status/{t.id}"
                alerts.append({
                    "title": "Twitter search hit: possible TGE",
                    "text": txt,
                    "url": url,
                    "published": (t.created_at.isoformat() if getattr(t, "created_at", None) else None),
                    "tweet_id": str(t.id),
                    "channel": "twitter",
                })
                if newest is None or int(t.id) > int(newest or 0):
                    newest = str(t.id)

            if newest is not None:
                self._since[key] = str(newest)
                _save_since_map(self._since)
            time.sleep(0.6)  # spacing between query groups

        return alerts

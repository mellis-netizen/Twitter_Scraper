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

from config import COMPANIES, TGE_KEYWORDS

# ------------------ persistent since_id per user/search ------------------

STATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "state")
SINCE_PATH = os.path.join(STATE_DIR, "twitter_since.json")


def _load_since_map() -> dict:
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        if os.path.isfile(SINCE_PATH):
            with open(SINCE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
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
    if not text:
        return False
    company_hit = False
    for c in COMPANIES:
        if isinstance(c, dict):
            names = [c.get("name", "")] + (c.get("aliases", []) or [])
        else:
            names = [str(c)]
        if any(_has_token(text, n) for n in names if n):
            company_hit = True
            break
    if not company_hit:
        return False
    keyword_hit = any(_has_token(text, k) for k in TGE_KEYWORDS)
    return company_hit and keyword_hit


def _call_with_backoff(fn, *args, **kwargs):
    delay = 60
    for _ in range(6):
        try:
            return fn(*args, **kwargs)
        except TooManyRequests:
            time.sleep(delay)
            delay = min(delay * 2, 15 * 60)
        except HTTPException:
            time.sleep(delay)
            delay = min(delay * 2, 10 * 60)
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

        bearer = os.getenv("TWITTER_BEARER_TOKEN")
        if not bearer:
            self.logger.warning("TWITTER_BEARER_TOKEN missing; Twitter monitoring disabled")
            self.client = None
            self.api = None
            self._since = {}
            self.accounts: list[str] = []
            self.search_enabled = False
            return

        self.client = tweepy.Client(bearer_token=bearer, wait_on_rate_limit=False)
        self.api = self.client  # maintain attribute used elsewhere

        # Accounts: prefer a config var if you have one; else env comma list
        env_users = os.getenv("TWITTER_USERS", "").strip()
        self.accounts = [u.strip().lstrip("@") for u in env_users.split(",") if u.strip()]  # e.g. "OffchainLabs,arbitrum"

        # Toggle search if desired (default on)
        self.search_enabled = os.getenv("TWITTER_ENABLE_SEARCH", "1") not in {"0", "false", "False"}

        self._since = _load_since_map()

    # -------- public API expected by main.py --------

    def process_tweets(self) -> List[Dict]:
        if not self.client:
            return []

        out: list[dict] = []

        # 1) timelines
        if self.accounts:
            for handle in self.accounts:
                try:
                    u = _call_with_backoff(self.client.get_user, username=handle, user_fields=["id"])
                except Exception as e:
                    self.logger.warning(f"get_user({handle}) failed: {e}")
                    continue
                user = (u.data or None)
                if not user:
                    continue
                uid = str(user.id)
                out.extend(self._fetch_user_timeline(uid, handle))
                time.sleep(0.4)  # gentle pacing

        # 2) combined queries (company AND keyword)
        if self.search_enabled:
            out.extend(self._search_company_keyword_batches())
        
        # annotate as twitter and shape minimal fields downstream expects
        for a in out:
            a.setdefault("source", "Twitter")
            a.setdefault("source_type", "twitter")

        # stats
        self.logger.info(f"process_tweets: produced {len(out)} candidate alerts")
        return out

    def get_recent_tge_tweets(self, hours: int = 24) -> List[Dict]:
        # Simple shim for daily summary; you can implement a cache if needed
        return []

    def get_stats(self) -> Dict:
        return {
            "total_processed": 0,             # fill if you maintain counters
            "total_tge_tweets": 0
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
            txt = t.text or ""
            if not _matches_company_and_keyword(txt):
                continue
            url = f"https://x.com/{handle}/status/{t.id}"
            alerts.append({
                "title": f"@{handle}: possible TGE signal",
                "text": txt,
                "url": url,
                "published": (t.created_at.isoformat() if getattr(t, "created_at", None) else None),
                "author": handle,
                "tweet_id": str(t.id),
                "channel": "twitter",
            })
            if newest is None or int(t.id) > int(newest or 0):
                newest = str(t.id)

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

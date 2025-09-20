"""
news_scraper.py (robust version)

- HTTP fetching with retries (requests + urllib3 Retry)
- Lenient RSS/Atom parsing (feedparser)
- Datetime normalization to timezone-aware UTC
- URL normalization/fallbacks for common crypto blogs (Coindesk, Ethereum blog, Ghost, Medium)
- Dedupe by link; newest-first sorting
"""

from typing import List, Dict, Optional
import logging
import calendar
from datetime import datetime, timezone, timedelta
import re

import requests
import feedparser
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dateutil import parser as dtp

# Project config (run with PYTHONPATH=.)
from config import COMPANIES, TGE_KEYWORDS, NEWS_SOURCES

# Module-level logger
log = logging.getLogger("news_scraper")

# Known URL remaps / fallbacks
# (We still try the original first; when it fails or is bad, we’ll try these)
FALLBACK_FEEDS = {
    # Coindesk category feeds often 403; fallback to the main feed
    "https://www.coindesk.com/arc/outboundfeeds/rss/category/ethereum": "https://www.coindesk.com/arc/outboundfeeds/rss",
    "https://www.coindesk.com/arc/outboundfeeds/rss/category/ethereum/": "https://www.coindesk.com/arc/outboundfeeds/rss",

    # Ethereum Foundation blog uses language feeds
    "https://blog.ethereum.org/feed": "https://blog.ethereum.org/en/feed.xml",
    "https://blog.ethereum.org/feed/": "https://blog.ethereum.org/en/feed.xml",

    # Ghost-powered sites (Fantom) usually expose /rss/
    "https://fantom.foundation/blog/feed/": "https://blog.fantom.foundation/rss/",
    "https://blog.fantom.foundation/blog/feed/": "https://blog.fantom.foundation/rss/",
}

MEDIUM_HOST_RE = re.compile(r"^https://([a-z0-9-]+)\.medium\.com/?$", re.I)
MEDIUM_PUB_RE = re.compile(r"^https://medium\.com/([^/@]+)/*$", re.I)
MEDIUM_USER_RE = re.compile(r"^https://medium\.com/@([^/]+)/*$", re.I)


def _normalize_feed_url(url: str) -> str:
    """
    - If URL matches a known problem, map to a better RSS.
    - If URL is a Medium space, construct the correct /feed variant:
      * publication: https://medium.com/<pub>  -> https://medium.com/feed/<pub>
      * user subdomain: https://<user>.medium.com -> https://<user>.medium.com/feed
      * user handle: https://medium.com/@user    -> https://medium.com/feed/@user
    We return the *normalized* candidate; the fetcher will still try the original first.
    """
    u = url.rstrip("/")

    # Known one-off fallbacks
    if u in FALLBACK_FEEDS:
        return FALLBACK_FEEDS[u]

    # Medium spaces
    if MEDIUM_HOST_RE.match(u):
        return f"{u}/feed"  # subdomain format
    m_pub = MEDIUM_PUB_RE.match(u)
    if m_pub:
        slug = m_pub.group(1)
        return f"https://medium.com/feed/{slug}"
    m_user = MEDIUM_USER_RE.match(u)
    if m_user:
        handle = m_user.group(1)
        return f"https://medium.com/feed/@{handle}"

    return url


def to_aware_utc(dt_val: Optional[object]) -> Optional[datetime]:
    """Coerce various datetime representations into tz-aware UTC."""
    if dt_val is None:
        return None
    if isinstance(dt_val, str):
        try:
            dt_val = dtp.parse(dt_val)
        except Exception:
            return None
    if not isinstance(dt_val, datetime):
        return None
    if dt_val.tzinfo is None:
        return dt_val.replace(tzinfo=timezone.utc)
    return dt_val.astimezone(timezone.utc)


_session: Optional[requests.Session] = None


def get_session() -> requests.Session:
    """Shared requests.Session with retry/backoff + friendly headers."""
    global _session
    if _session is None:
        s = requests.Session()
        s.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; TGE-Monitor/1.0; +https://example.com/bot)",
            "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8",
        })
        retry = Retry(
            total=3,
            backoff_factor=0.6,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"],
        )
        s.mount("http://", HTTPAdapter(max_retries=retry))
        s.mount("https://", HTTPAdapter(max_retries=retry))
        _session = s
    return _session


def _parse_entries(content: bytes, url: str, logger: logging.Logger, limit: int) -> List[Dict]:
    parsed = feedparser.parse(content)
    if getattr(parsed, "bozo", False):
        logger.warning("RSS feed parsing warning for %s: %s", url, getattr(parsed, "bozo_exception", "unknown"))

    items: List[Dict] = []
    max_items = max(1, min(limit, 200))
    for e in parsed.entries[:max_items]:
        dt: Optional[datetime] = None
        for key in ("published", "updated", "created"):
            dt = to_aware_utc(e.get(key))
            if dt:
                break
        if not dt and getattr(e, "published_parsed", None):
            ts = calendar.timegm(e.published_parsed)  # treat struct_time as UTC
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)

        items.append(
            {
                "title": (e.get("title") or "").strip(),
                "link": e.get("link"),
                "summary": e.get("summary", ""),
                "published": dt,
                "source": url,
            }
        )
    return items


def fetch_feed(url: str, timeout: int = 15, limit: int = 50, logger: Optional[logging.Logger] = None) -> List[Dict]:
    """
    Lenient fetch + parse for a single RSS/Atom URL with a single fallback try.
    Returns list of dicts: {title, link, summary, published(datetime UTC), source}
    """
    L = logger or log
    sess = get_session()

    def _try(u: str) -> List[Dict]:
        resp = sess.get(u, timeout=timeout)
        resp.raise_for_status()
        return _parse_entries(resp.content, u, L, limit)

    # Try original
    try:
        return _try(url)
    except requests.HTTPError as ex:
        # Log and consider a normalized fallback for 4xx/5xx
        L.error("Error fetching RSS feed %s: %s", url, ex)
        fallback = _normalize_feed_url(url)
        if fallback and fallback != url:
            try:
                L.info("Retrying with normalized feed URL: %s -> %s", url, fallback)
                return _try(fallback)
            except Exception as ex2:
                L.error("Fallback feed also failed %s: %s", fallback, ex2)
                return []
        return []
    except requests.RequestException as ex:
        L.error("Error fetching RSS feed %s: %s", url, ex)
        # name resolution or other network issues: still attempt normalized
        fallback = _normalize_feed_url(url)
        if fallback and fallback != url:
            try:
                L.info("Retrying with normalized feed URL: %s -> %s", url, fallback)
                return _try(fallback)
            except Exception as ex2:
                L.error("Fallback feed also failed %s: %s", fallback, ex2)
                return []
        return []


class NewsScraper:
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or log
        # expose session for health checks
        try:
            self.session = get_session()
        except Exception:
            self.session = None

        self.total_processed = 0
        self.total_tge_articles = 0
        self._history: List[Dict] = []  # alerts we've emitted (with 'published')

    def fetch_rss_feeds(self, urls: List[str], limit_per_feed: int = 50, max_results: int = 100) -> List[Dict]:
        """
        Fetch all feeds in `urls`, normalize datetimes to aware UTC, dedupe by link,
        and return newest-first list of items. Each item:
        {title, link, summary, published (aware UTC dt), source}
        """
        all_items: List[Dict] = []
        for raw_url in urls:
            self.logger.info("Fetching RSS feed: %s", raw_url)
            entries = fetch_feed(raw_url, limit=limit_per_feed, logger=self.logger)
            if not entries:
                self.logger.warning("No entries parsed for %s", raw_url)
            all_items.extend(entries)

        # Keep only items with a date
        items = [i for i in all_items if i.get("published")]

        # Dedupe by link; fallback to (source, title)
        seen = set()
        unique: List[Dict] = []
        for it in items:
            key = it.get("link") or (it.get("source"), it.get("title"))
            if key in seen:
                continue
            seen.add(key)
            unique.append(it)

        # Newest first
        unique.sort(key=lambda x: x["published"], reverse=True)

        self.logger.info("Fetched %d recent articles", len(unique))
        return unique[:max_results] if max_results else unique

    def process_articles(self) -> List[Dict]:
        """
        Fetch all configured sources, detect TGE-related items, and
        return a list of alert dicts suitable for the email notifier.
        """
        # 1) fetch
        articles = self.fetch_rss_feeds(NEWS_SOURCES, limit_per_feed=50, max_results=200)

        # 2) detect mentions
        companies_lower = [c.lower() for c in COMPANIES]
        keywords_lower = [k.lower() for k in TGE_KEYWORDS]

        alerts: List[Dict] = []
        for a in articles:
            title = a.get("title") or ""
            summary = a.get("summary") or ""
            blob = f"{title}\n{summary}".lower()

            mentioned_companies = sorted({c for c in companies_lower if c and c in blob})
            found_keywords = sorted({k for k in keywords_lower if k and k in blob})

            if not (mentioned_companies or found_keywords):
                continue

            # lightweight relevance
            score = 2.0 * len(mentioned_companies) + 1.0 * len(found_keywords)

            alert = {
                "title": title,
                "link": a.get("link"),
                "summary": summary,
                "published": a.get("published"),  # aware UTC dt (from fetcher)
                "source": a.get("source"),
                "mentioned_companies": [c for c in mentioned_companies],
                "found_keywords": [k for k in found_keywords],
                "relevance_score": score,
            }
            alerts.append(alert)

        # stats + rolling history (dedupe by link)
        self.total_processed += len(articles)
        self.total_tge_articles += len(alerts)

        seen = set()
        new_hist: List[Dict] = []
        for it in (alerts + self._history):
            key = it.get("link") or (it.get("source"), it.get("title"))
            if key in seen:
                continue
            seen.add(key)
            new_hist.append(it)
        self._history = new_hist[:500]

        return alerts

    def get_recent_tge_articles(self, hours: int) -> List[Dict]:
        """Return TGE alerts seen within the last `hours` hours."""
        if not self._history:
            return []
        try:
            now = datetime.now(timezone.utc)
        except Exception:
            now = datetime.utcnow().replace(tzinfo=timezone.utc)
        cutoff = now - timedelta(hours=hours)
        out = []
        for it in self._history:
            dt = it.get("published")
            if dt is None:
                continue
            try:
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            except Exception:
                continue
            if dt >= cutoff:
                out.append(it)
        out.sort(key=lambda x: x.get("published") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        return out

    def get_stats(self) -> Dict:
        return {
            "total_processed": int(self.total_processed),
            "total_tge_articles": int(self.total_tge_articles),
        }


# Optional: local test harness
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    test_urls = [
        "https://decrypt.co/feed",
        "https://www.theblock.co/rss.xml",
        "https://www.coindesk.com/arc/outboundfeeds/rss/category/ethereum/",
        "https://thedefiant.io/feed",
        "https://www.dlnews.com/arc/outboundfeeds/rss/",
        "https://blog.ethereum.org/feed",                # will normalize -> /en/feed.xml
        "https://blog.fantom.foundation/blog/feed/",     # will normalize -> /rss/
        "https://medium.com/avalancheavax",              # will normalize -> /feed/avalancheavax
        "https://avalancheavax.medium.com",              # will normalize -> /feed
        "https://medium.com/@telosfoundation",           # will normalize -> /feed/@telosfoundation
    ]
    scraper = NewsScraper()
    articles = scraper.fetch_rss_feeds(test_urls)
    for a in articles[:10]:
        print(a["published"], "-", a["title"])

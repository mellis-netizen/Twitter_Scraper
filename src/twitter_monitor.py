"""
Twitter Monitoring Module for Crypto TGE Events

This module handles Twitter API integration to monitor crypto-related accounts
for TGE announcements and relevant news.
"""

import tweepy
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Set, Optional
import time
import re
import json
import os

from config import TWITTER_CONFIG, TWITTER_ACCOUNTS, COMPANIES, TGE_KEYWORDS
from utils import (
    retry_on_failure, generate_content_hash, is_content_duplicate,
    sanitize_text, calculate_relevance_score, is_recent_content,
    save_json_file, load_json_file, truncate_text
)


class TwitterMonitor:
    """Class for monitoring Twitter accounts for TGE-related content."""
    
    def __init__(self, state_file: str = 'logs/twitter_monitor_state.json'):
        self.setup_logging()
        self.api = None
        self.client = None
        self.processed_tweets = set()
        self.tge_tweets = []
        self.seen_content_hashes = set()
        self.state_file = state_file
        
        # Load persistent state
        self.load_state()
        
        self._setup_twitter_api()
        self.logger.info("TwitterMonitor initialized successfully")
    
    def setup_logging(self):
        """Setup logging configuration."""
        self.logger = logging.getLogger(__name__)
    
    def load_state(self):
        """Load persistent state from file."""
        state = load_json_file(self.state_file, {})
        if state:
            self.processed_tweets = set(state.get('processed_tweets', []))
            self.seen_content_hashes = set(state.get('seen_content_hashes', []))
            self.tge_tweets = state.get('tge_tweets', [])
            self.logger.info(f"Loaded state: {len(self.processed_tweets)} processed tweets, {len(self.tge_tweets)} TGE tweets")
    
    def save_state(self):
        """Save persistent state to file."""
        state = {
            'processed_tweets': list(self.processed_tweets),
            'seen_content_hashes': list(self.seen_content_hashes),
            'tge_tweets': self.tge_tweets,
            'last_updated': datetime.now().isoformat()
        }
        if save_json_file(self.state_file, state):
            self.logger.debug("State saved successfully")
        else:
            self.logger.warning("Failed to save state")
    
    def _setup_twitter_api(self):
        """Initialize Twitter API client."""
        try:
            # Check if we have the required credentials
            if not all([
                TWITTER_CONFIG.get('api_key'),
                TWITTER_CONFIG.get('api_secret'),
                TWITTER_CONFIG.get('access_token'),
                TWITTER_CONFIG.get('access_token_secret')
            ]):
                self.logger.warning("Twitter API credentials not fully configured. Twitter monitoring will be disabled.")
                return
            
            # Initialize Tweepy API v1.1 (for user timeline access)
            auth = tweepy.OAuth1UserHandler(
                TWITTER_CONFIG['api_key'],
                TWITTER_CONFIG['api_secret'],
                TWITTER_CONFIG['access_token'],
                TWITTER_CONFIG['access_token_secret']
            )
            self.api = tweepy.API(auth, wait_on_rate_limit=True)
            
            # Initialize Tweepy Client v2 (for better search capabilities)
            if TWITTER_CONFIG.get('bearer_token'):
                self.client = tweepy.Client(
                    bearer_token=TWITTER_CONFIG['bearer_token'],
                    wait_on_rate_limit=True
                )
            
            self.logger.info("Twitter API initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Twitter API: {str(e)}")
            self.api = None
            self.client = None
    
    @retry_on_failure(max_retries=2, delay=5.0, exceptions=(tweepy.TooManyRequests, tweepy.TwitterServerError))
    def fetch_user_tweets(self, username: str, count: int = 50) -> List[Dict]:
        """Fetch recent tweets from a specific user."""
        if not self.api:
            self.logger.warning("Twitter API not available")
            return []
        
        try:
            # Remove @ symbol if present
            username = username.lstrip('@')
            
            tweets = []
            user_tweets = tweepy.Cursor(
                self.api.user_timeline,
                screen_name=username,
                count=count,
                tweet_mode='full',
                include_rts=False,
                exclude_replies=True
            ).items(count)
            
            for tweet in user_tweets:
                tweet_data = {
                    'id': tweet.id_str,
                    'text': sanitize_text(tweet.full_text),
                    'created_at': tweet.created_at,
                    'user': {
                        'screen_name': tweet.user.screen_name,
                        'name': tweet.user.name,
                        'followers_count': tweet.user.followers_count
                    },
                    'retweet_count': tweet.retweet_count,
                    'favorite_count': tweet.favorite_count,
                    'url': f"https://twitter.com/{username}/status/{tweet.id_str}"
                }
                tweets.append(tweet_data)
            
            self.logger.info(f"Fetched {len(tweets)} tweets from @{username}")
            return tweets
            
        except tweepy.TooManyRequests:
            self.logger.warning(f"Rate limit exceeded for @{username}")
            return []
        except tweepy.NotFound:
            self.logger.warning(f"User @{username} not found")
            return []
        except Exception as e:
            self.logger.error(f"Error fetching tweets from @{username}: {str(e)}")
            return []
    
    def search_tweets(self, query: str, count: int = 100) -> List[Dict]:
        """Search for tweets using Twitter API v2."""
        if not self.client:
            self.logger.warning("Twitter Client v2 not available")
            return []
        
        try:
            # Search for recent tweets
            tweets = self.client.search_recent_tweets(
                query=query,
                max_results=min(count, 100),  # API limit
                tweet_fields=['created_at', 'public_metrics', 'author_id'],
                user_fields=['username', 'name', 'public_metrics'],
                expansions=['author_id']
            )
            
            if not tweets.data:
                return []
            
            # Process tweets
            processed_tweets = []
            users = {user.id: user for user in tweets.includes.get('users', [])}
            
            for tweet in tweets.data:
                author = users.get(tweet.author_id)
                tweet_data = {
                    'id': tweet.id,
                    'text': tweet.text,
                    'created_at': tweet.created_at,
                    'user': {
                        'screen_name': author.username if author else 'unknown',
                        'name': author.name if author else 'unknown',
                        'followers_count': author.public_metrics['followers_count'] if author and author.public_metrics else 0
                    },
                    'retweet_count': tweet.public_metrics['retweet_count'],
                    'favorite_count': tweet.public_metrics['like_count'],
                    'url': f"https://twitter.com/{author.username if author else 'unknown'}/status/{tweet.id}"
                }
                processed_tweets.append(tweet_data)
            
            self.logger.info(f"Found {len(processed_tweets)} tweets for query: {query}")
            return processed_tweets
            
        except Exception as e:
            self.logger.error(f"Error searching tweets for query '{query}': {str(e)}")
            return []
    
    def monitor_accounts(self) -> List[Dict]:
        """Monitor all configured Twitter accounts for TGE-related content."""
        all_tweets = []
        
        for account in TWITTER_ACCOUNTS:
            try:
                tweets = self.fetch_user_tweets(account, count=20)
                all_tweets.extend(tweets)
                
                # Rate limiting
                time.sleep(1)
                
            except Exception as e:
                self.logger.error(f"Error monitoring account {account}: {str(e)}")
                continue
        
        return all_tweets
    
    def search_tge_keywords(self) -> List[Dict]:
        """Search for tweets containing TGE-related keywords."""
        all_tweets = []
        
        # Create search queries combining companies and TGE keywords
        search_queries = []
        
        # Search for each company with TGE keywords
        for company in COMPANIES[:10]:  # Limit to avoid rate limits
            for keyword in TGE_KEYWORDS[:5]:  # Limit keywords
                query = f'"{company}" {keyword} -is:retweet lang:en'
                search_queries.append(query)
        
        # Also search for general TGE terms
        general_queries = [
            'TGE token generation event -is:retweet lang:en',
            'crypto token launch -is:retweet lang:en',
            'airdrop announcement -is:retweet lang:en',
            'token sale ICO IDO -is:retweet lang:en'
        ]
        search_queries.extend(general_queries)
        
        for query in search_queries:
            try:
                tweets = self.search_tweets(query, count=20)
                all_tweets.extend(tweets)
                
                # Rate limiting
                time.sleep(2)
                
            except Exception as e:
                self.logger.error(f"Error searching with query '{query}': {str(e)}")
                continue
        
        return all_tweets
    
    def analyze_tweet_for_tge(self, tweet: Dict) -> Dict:
        """Analyze a tweet for TGE-related content."""
        text = tweet['text']
        
        # Check for content duplication
        if is_content_duplicate(text, self.seen_content_hashes):
            self.logger.debug(f"Duplicate content detected for tweet: {tweet['id']}")
            return {
                'tweet': tweet,
                'mentioned_companies': [],
                'found_keywords': [],
                'relevance_score': 0.0,
                'is_tge_related': False,
                'analysis_timestamp': datetime.now(),
                'is_duplicate': True
            }
        
        text_lower = text.lower()
        
        # Check for company mentions
        mentioned_companies = []
        for company in COMPANIES:
            if company.lower() in text_lower:
                mentioned_companies.append(company)
        
        # Check for TGE keywords
        found_keywords = []
        for keyword in TGE_KEYWORDS:
            if keyword.lower() in text_lower:
                found_keywords.append(keyword)
        
        # Calculate relevance score with custom weights for tweets
        keyword_weights = {
            'tge': 0.5,
            'token generation event': 0.5,
            'token launch': 0.4,
            'airdrop': 0.3,
            'token sale': 0.25,
            'ico': 0.25,
            'ido': 0.25,
            'token listing': 0.2,
            'token distribution': 0.2
        }
        
        relevance_score = calculate_relevance_score(
            mentioned_companies, found_keywords, text,
            keyword_weights=keyword_weights,
            company_weight=0.4
        )
        
        # Add engagement boost for tweets
        engagement_score = (
            tweet.get('retweet_count', 0) * 0.001 +
            tweet.get('favorite_count', 0) * 0.0005
        )
        relevance_score += min(engagement_score, 0.2)
        
        # Follower count boost
        followers = tweet.get('user', {}).get('followers_count', 0)
        if followers > 100000:
            relevance_score += 0.1
        elif followers > 10000:
            relevance_score += 0.05
        
        relevance_score = min(relevance_score, 1.0)
        
        # Determine if this is likely a TGE announcement
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
            'analysis_timestamp': datetime.now(),
            'is_duplicate': False
        }
    
    def process_tweets(self) -> List[Dict]:
        """Process all fetched tweets and identify TGE-related content."""
        # Get tweets from monitored accounts
        account_tweets = self.monitor_accounts()
        
        # Get tweets from keyword searches
        search_tweets = self.search_tge_keywords()
        
        # Combine and deduplicate
        all_tweets = account_tweets + search_tweets
        unique_tweets = {tweet['id']: tweet for tweet in all_tweets}.values()
        
        tge_tweets = []
        
        for tweet in unique_tweets:
            # Skip if already processed
            if tweet['id'] in self.processed_tweets:
                continue
            
            self.processed_tweets.add(tweet['id'])
            
            # Only process recent tweets (last 24 hours)
            if not is_recent_content(tweet['created_at'], hours=24):
                continue
            
            # Analyze tweet
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
        
        # Save state after processing
        self.save_state()
        
        return tge_tweets
    
    def get_recent_tge_tweets(self, hours: int = 24) -> List[Dict]:
        """Get TGE tweets from the last N hours."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [
            tweet for tweet in self.tge_tweets
            if tweet['tweet']['created_at'] > cutoff_time
        ]
    
    def format_tweet_alert(self, analysis: Dict) -> str:
        """Format TGE tweet analysis into a readable alert."""
        tweet = analysis['tweet']
        
        alert = f"""
🐦 TGE TWEET ALERT - @{tweet['user']['screen_name']}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

👤 User: {tweet['user']['name']} (@{tweet['user']['screen_name']})
👥 Followers: {tweet['user']['followers_count']:,}
📅 Posted: {tweet['created_at'].strftime('%Y-%m-%d %H:%M UTC')}
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
            'unique_content_hashes': len(self.seen_content_hashes)
        }
    
if __name__ == "__main__":
    monitor = TwitterMonitor()
    tge_tweets = monitor.process_tweets()
    
    print(f"Found {len(tge_tweets)} TGE-related tweets")
    for analysis in tge_tweets:
        print(monitor.format_tweet_alert(analysis))
        print("\n" + "="*50 + "\n")

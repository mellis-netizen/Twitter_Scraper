"""
Crypto TGE News Scraper Module

This module handles RSS feed monitoring, content analysis, and TGE detection
for cryptocurrency token generation events.
"""

import feedparser
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Set, Optional
from urllib.parse import urljoin, urlparse
import time
import re
from bs4 import BeautifulSoup
from newspaper import Article
import nltk
from textblob import TextBlob
import json
import os

from config import COMPANIES, TGE_KEYWORDS, NEWS_SOURCES, LOG_CONFIG
from utils import (
    create_robust_session, retry_on_failure, generate_content_hash,
    is_content_duplicate, validate_url, sanitize_text, parse_date_flexible,
    extract_domain, truncate_text, calculate_relevance_score,
    is_recent_content, save_json_file, load_json_file
)


class NewsScraper:
    """Main class for scraping and analyzing crypto news for TGE events."""
    
    def __init__(self, state_file: str = 'logs/news_scraper_state.json'):
        self.setup_logging()
        self.session = create_robust_session()
        self.processed_articles = set()
        self.tge_articles = []
        self.seen_content_hashes = set()
        self.state_file = state_file
        
        # Load persistent state
        self.load_state()
        
        # Download required NLTK data
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            nltk.download('punkt')
        
        self.logger.info("NewsScraper initialized successfully")
    
    def setup_logging(self):
        """Setup logging configuration."""
        self.logger = logging.getLogger(__name__)
    
    def load_state(self):
        """Load persistent state from file."""
        state = load_json_file(self.state_file, {})
        if state:
            self.processed_articles = set(state.get('processed_articles', []))
            self.seen_content_hashes = set(state.get('seen_content_hashes', []))
            self.tge_articles = state.get('tge_articles', [])
            self.logger.info(f"Loaded state: {len(self.processed_articles)} processed articles, {len(self.tge_articles)} TGE articles")
    
    def save_state(self):
        """Save persistent state to file."""
        state = {
            'processed_articles': list(self.processed_articles),
            'seen_content_hashes': list(self.seen_content_hashes),
            'tge_articles': self.tge_articles,
            'last_updated': datetime.now().isoformat()
        }
        if save_json_file(self.state_file, state):
            self.logger.debug("State saved successfully")
        else:
            self.logger.warning("Failed to save state")
    
    @retry_on_failure(max_retries=3, delay=2.0, exceptions=(Exception,))
    def fetch_rss_feeds(self) -> List[Dict]:
        """Fetch articles from all configured RSS feeds."""
        all_articles = []
        
        for source_url in NEWS_SOURCES:
            try:
                if not validate_url(source_url):
                    self.logger.warning(f"Invalid RSS feed URL: {source_url}")
                    continue
                
                self.logger.info(f"Fetching RSS feed: {source_url}")
                feed = feedparser.parse(source_url)
                
                if feed.bozo:
                    self.logger.warning(f"RSS feed parsing warning for {source_url}: {feed.bozo_exception}")
                
                for entry in feed.entries:
                    article = {
                        'title': sanitize_text(entry.get('title', '')),
                        'link': entry.get('link', ''),
                        'published': parse_date_flexible(entry.get('published', '')),
                        'summary': sanitize_text(entry.get('summary', '')),
                        'source': source_url,
                        'source_name': extract_domain(source_url)
                    }
                    
                    # Validate article data
                    if not article['title'] or not article['link']:
                        continue
                    
                    # Only process recent articles (last 24 hours)
                    if is_recent_content(article['published'], hours=24):
                        all_articles.append(article)
                
                # Rate limiting
                time.sleep(1)
                
            except Exception as e:
                self.logger.error(f"Error fetching RSS feed {source_url}: {str(e)}")
                continue
        
        self.logger.info(f"Fetched {len(all_articles)} recent articles")
        return all_articles
    
    @retry_on_failure(max_retries=2, delay=1.0, exceptions=(Exception,))
    def fetch_article_content(self, article: Dict) -> str:
        """Fetch full article content from the article URL."""
        try:
            if not validate_url(article['link']):
                return article.get('summary', '')
            
            response = self.session.get(article['link'], timeout=15)
            response.raise_for_status()
            
            # Try using newspaper3k for better content extraction
            try:
                article_obj = Article(article['link'])
                article_obj.download()
                article_obj.parse()
                return sanitize_text(article_obj.text, max_length=5000)
            except Exception:
                # Fallback to BeautifulSoup
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Remove script and style elements
                for script in soup(["script", "style", "nav", "footer", "header"]):
                    script.decompose()
                
                # Try to find main content
                content_selectors = [
                    'article', '.article-content', '.post-content', 
                    '.entry-content', '.content', 'main', '.main-content',
                    '.story-body', '.article-body', '.post-body'
                ]
                
                for selector in content_selectors:
                    content = soup.select_one(selector)
                    if content:
                        return sanitize_text(content.get_text(strip=True), max_length=5000)
                
                # Fallback to body text
                return sanitize_text(soup.get_text(strip=True), max_length=5000)
                
        except Exception as e:
            self.logger.error(f"Error fetching article content from {article['link']}: {str(e)}")
            return article.get('summary', '')
    
    def analyze_article_for_tge(self, article: Dict) -> Dict:
        """Analyze article for TGE-related content."""
        # Combine title, summary, and content for analysis
        full_text = f"{article['title']} {article.get('summary', '')}"
        
        # Fetch full content if we have a link
        if article.get('link'):
            content = self.fetch_article_content(article)
            full_text += f" {content}"
        
        # Check for content duplication
        if is_content_duplicate(full_text, self.seen_content_hashes):
            self.logger.debug(f"Duplicate content detected for article: {article['title']}")
            return {
                'article': article,
                'mentioned_companies': [],
                'found_keywords': [],
                'relevance_score': 0.0,
                'is_tge_related': False,
                'analysis_timestamp': datetime.now(),
                'is_duplicate': True
            }
        
        # Convert to lowercase for case-insensitive matching
        text_lower = full_text.lower()
        
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
        
        # Calculate TGE relevance score
        relevance_score = calculate_relevance_score(
            mentioned_companies, found_keywords, full_text
        )
        
        # Determine if this is likely a TGE announcement
        is_tge_related = (
            len(mentioned_companies) > 0 and 
            len(found_keywords) > 0 and 
            relevance_score > 0.3
        )
        
        return {
            'article': article,
            'mentioned_companies': mentioned_companies,
            'found_keywords': found_keywords,
            'relevance_score': relevance_score,
            'is_tge_related': is_tge_related,
            'analysis_timestamp': datetime.now(),
            'is_duplicate': False
        }
    
    def process_articles(self) -> List[Dict]:
        """Process all fetched articles and identify TGE-related content."""
        articles = self.fetch_rss_feeds()
        tge_articles = []
        
        for article in articles:
            # Skip if already processed
            article_id = f"{article['link']}_{article['published']}"
            if article_id in self.processed_articles:
                continue
            
            self.processed_articles.add(article_id)
            
            # Analyze article
            analysis = self.analyze_article_for_tge(article)
            
            if analysis['is_tge_related'] and not analysis.get('is_duplicate', False):
                tge_articles.append(analysis)
                self.logger.info(
                    f"TGE-related article found: {article['title']} "
                    f"(Companies: {analysis['mentioned_companies']}, "
                    f"Score: {analysis['relevance_score']:.2f})"
                )
        
        self.tge_articles.extend(tge_articles)
        
        # Save state after processing
        self.save_state()
        
        return tge_articles
    
    def get_recent_tge_articles(self, hours: int = 24) -> List[Dict]:
        """Get TGE articles from the last N hours."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [
            article for article in self.tge_articles
            if article['article']['published'] and article['article']['published'] > cutoff_time
        ]
    
    def format_tge_alert(self, analysis: Dict) -> str:
        """Format TGE analysis into a readable alert."""
        article = analysis['article']
        
        alert = f"""
🚀 TGE ALERT - {article['source_name']}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📰 Title: {article['title']}
🔗 Link: {article['link']}
📅 Published: {article['published'].strftime('%Y-%m-%d %H:%M UTC') if article['published'] else 'Unknown'}

🏢 Companies Mentioned: {', '.join(analysis['mentioned_companies']) if analysis['mentioned_companies'] else 'None'}
🔑 TGE Keywords: {', '.join(analysis['found_keywords']) if analysis['found_keywords'] else 'None'}
📊 Relevance Score: {analysis['relevance_score']:.2f}/1.0

📝 Summary:
{truncate_text(article.get('summary', 'No summary available'), 300)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        """
        
        return alert.strip()
    
    def get_stats(self) -> Dict[str, int]:
        """Get statistics about processed articles."""
        return {
            'total_processed': len(self.processed_articles),
            'total_tge_articles': len(self.tge_articles),
            'recent_tge_articles': len(self.get_recent_tge_articles(24)),
            'unique_content_hashes': len(self.seen_content_hashes)
        }
    
if __name__ == "__main__":
    scraper = NewsScraper()
    tge_articles = scraper.process_articles()
    
    print(f"Found {len(tge_articles)} TGE-related articles")
    for analysis in tge_articles:
        print(scraper.format_tge_alert(analysis))
        print("\n" + "="*50 + "\n")

#!/usr/bin/env python3
"""
Test script for Crypto TGE Monitor system
"""

import sys
import os
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

def test_imports():
    """Test that all modules can be imported."""
    print("🔄 Testing imports...")
    
    try:
        from news_scraper import NewsScraper
        print("✅ NewsScraper imported")
    except Exception as e:
        print(f"❌ NewsScraper import failed: {e}")
        return False
    
    try:
        from twitter_monitor import TwitterMonitor
        print("✅ TwitterMonitor imported")
    except Exception as e:
        print(f"❌ TwitterMonitor import failed: {e}")
        return False
    
    try:
        from email_notifier import EmailNotifier
        print("✅ EmailNotifier imported")
    except Exception as e:
        print(f"❌ EmailNotifier import failed: {e}")
        return False
    
    try:
        from main import CryptoTGEMonitor
        print("✅ CryptoTGEMonitor imported")
    except Exception as e:
        print(f"❌ CryptoTGEMonitor import failed: {e}")
        return False
    
    return True


def test_news_scraper():
    """Test news scraper functionality."""
    print("\n🔄 Testing news scraper...")
    
    try:
        from news_scraper import NewsScraper
        scraper = NewsScraper()
        
        # Test RSS feed fetching (limited to avoid rate limits)
        print("  - Testing RSS feed fetching...")
        articles = scraper.fetch_rss_feeds()
        print(f"  ✅ Fetched {len(articles)} articles")
        
        # Test article analysis
        if articles:
            print("  - Testing article analysis...")
            analysis = scraper.analyze_article_for_tge(articles[0])
            print(f"  ✅ Analysis completed (score: {analysis['relevance_score']:.2f})")
        
        return True
    except Exception as e:
        print(f"  ❌ News scraper test failed: {e}")
        return False


def test_twitter_monitor():
    """Test Twitter monitor functionality."""
    print("\n🔄 Testing Twitter monitor...")
    
    try:
        from twitter_monitor import TwitterMonitor
        monitor = TwitterMonitor()
        
        if monitor.api is None:
            print("  ⚠️  Twitter API not configured (this is optional)")
            return True
        
        print("  ✅ Twitter API initialized")
        return True
    except Exception as e:
        print(f"  ❌ Twitter monitor test failed: {e}")
        return False


def test_email_notifier():
    """Test email notifier functionality."""
    print("\n🔄 Testing email notifier...")
    
    try:
        from email_notifier import EmailNotifier
        notifier = EmailNotifier()
        
        if not notifier.enabled:
            print("  ⚠️  Email not configured (this is required for notifications)")
            return True
        
        print("  ✅ Email notifier initialized")
        return True
    except Exception as e:
        print(f"  ❌ Email notifier test failed: {e}")
        return False


def test_config():
    """Test configuration loading."""
    print("\n🔄 Testing configuration...")
    
    try:
        from config import COMPANIES, TGE_KEYWORDS, NEWS_SOURCES, TWITTER_ACCOUNTS
        print(f"  ✅ Companies: {len(COMPANIES)}")
        print(f"  ✅ TGE Keywords: {len(TGE_KEYWORDS)}")
        print(f"  ✅ News Sources: {len(NEWS_SOURCES)}")
        print(f"  ✅ Twitter Accounts: {len(TWITTER_ACCOUNTS)}")
        return True
    except Exception as e:
        print(f"  ❌ Configuration test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("🧪 Crypto TGE Monitor System Test")
    print("=" * 40)
    
    tests = [
        test_imports,
        test_config,
        test_news_scraper,
        test_twitter_monitor,
        test_email_notifier
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print("\n" + "=" * 40)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! System is ready to use.")
        print("\nNext steps:")
        print("1. Configure .env file with your credentials")
        print("2. Run: python run.py --mode test")
        print("3. Run: python run.py --mode once")
    else:
        print("⚠️  Some tests failed. Please check the errors above.")
        print("Make sure all dependencies are installed: pip install -r requirements.txt")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)


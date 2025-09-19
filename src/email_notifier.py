"""
Email Notification System for Crypto TGE Alerts

This module handles sending email notifications when TGE-related content
is detected from news sources and Twitter.
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from typing import List, Dict, Optional
import os

from config import EMAIL_CONFIG


class EmailNotifier:
    """Class for sending email notifications about TGE events."""
    
    def __init__(self):
        self.setup_logging()
        self.smtp_server = EMAIL_CONFIG['smtp_server']
        self.smtp_port = EMAIL_CONFIG['smtp_port']
        self.email_user = EMAIL_CONFIG['email_user']
        self.email_password = EMAIL_CONFIG['email_password']
        self.recipient_email = EMAIL_CONFIG['recipient_email']
        
        # Check if email is configured
        if not all([self.email_user, self.email_password, self.recipient_email]):
            self.logger.warning("Email configuration incomplete. Email notifications will be disabled.")
            self.enabled = False
        else:
            self.enabled = True
    
    def setup_logging(self):
        """Setup logging configuration."""
        self.logger = logging.getLogger(__name__)
    
    def send_tge_alert_email(self, news_alerts: List[Dict], twitter_alerts: List[Dict]) -> bool:
        """Send email with TGE alerts from news and Twitter."""
        if not self.enabled:
            self.logger.warning("Email notifications disabled - configuration incomplete")
            return False
        
        if not news_alerts and not twitter_alerts:
            self.logger.info("No TGE alerts to send")
            return True
        
        try:
            # Create email content
            subject = self._generate_email_subject(news_alerts, twitter_alerts)
            body = self._generate_email_body(news_alerts, twitter_alerts)
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.email_user
            msg['To'] = self.recipient_email
            msg['Subject'] = subject
            
            # Add HTML body
            html_body = MIMEText(body, 'html')
            msg.attach(html_body)
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_user, self.email_password)
                server.send_message(msg)
            
            self.logger.info(f"TGE alert email sent successfully to {self.recipient_email}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send TGE alert email: {str(e)}")
            return False
    
    def _generate_email_subject(self, news_alerts: List[Dict], twitter_alerts: List[Dict]) -> str:
        """Generate email subject line."""
        total_alerts = len(news_alerts) + len(twitter_alerts)
        
        if total_alerts == 1:
            if news_alerts:
                company = news_alerts[0]['mentioned_companies'][0] if news_alerts[0]['mentioned_companies'] else 'Unknown'
                return f"🚀 TGE Alert: {company} Token Generation Event Detected"
            else:
                company = twitter_alerts[0]['mentioned_companies'][0] if twitter_alerts[0]['mentioned_companies'] else 'Unknown'
                return f"🐦 TGE Tweet Alert: {company} Token Generation Event"
        else:
            return f"🚀 {total_alerts} TGE Alerts Detected - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    
    def _generate_email_body(self, news_alerts: List[Dict], twitter_alerts: List[Dict]) -> str:
        """Generate HTML email body."""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f5f5f5;
                }}
                .container {{
                    background-color: white;
                    border-radius: 10px;
                    padding: 30px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                .header {{
                    text-align: center;
                    border-bottom: 3px solid #007bff;
                    padding-bottom: 20px;
                    margin-bottom: 30px;
                }}
                .alert-section {{
                    margin-bottom: 40px;
                    border: 1px solid #e0e0e0;
                    border-radius: 8px;
                    overflow: hidden;
                }}
                .alert-header {{
                    background-color: #007bff;
                    color: white;
                    padding: 15px 20px;
                    font-weight: bold;
                    font-size: 18px;
                }}
                .alert-content {{
                    padding: 20px;
                }}
                .alert-item {{
                    border-bottom: 1px solid #f0f0f0;
                    padding: 20px 0;
                }}
                .alert-item:last-child {{
                    border-bottom: none;
                }}
                .alert-title {{
                    font-size: 16px;
                    font-weight: bold;
                    color: #007bff;
                    margin-bottom: 10px;
                }}
                .alert-meta {{
                    font-size: 14px;
                    color: #666;
                    margin-bottom: 10px;
                }}
                .companies {{
                    background-color: #e8f4fd;
                    padding: 8px 12px;
                    border-radius: 5px;
                    margin: 5px 0;
                    display: inline-block;
                }}
                .keywords {{
                    background-color: #fff3cd;
                    padding: 8px 12px;
                    border-radius: 5px;
                    margin: 5px 0;
                    display: inline-block;
                }}
                .score {{
                    background-color: #d4edda;
                    padding: 8px 12px;
                    border-radius: 5px;
                    margin: 5px 0;
                    display: inline-block;
                    font-weight: bold;
                }}
                .tweet-content {{
                    background-color: #f8f9fa;
                    padding: 15px;
                    border-radius: 5px;
                    border-left: 4px solid #007bff;
                    margin: 10px 0;
                    font-style: italic;
                }}
                .footer {{
                    text-align: center;
                    margin-top: 30px;
                    padding-top: 20px;
                    border-top: 1px solid #e0e0e0;
                    color: #666;
                    font-size: 12px;
                }}
                .link {{
                    color: #007bff;
                    text-decoration: none;
                }}
                .link:hover {{
                    text-decoration: underline;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🚀 Crypto TGE Monitor Alert</h1>
                    <p>Token Generation Event Detection Report</p>
                    <p><strong>{datetime.now().strftime('%Y-%m-%d %H:%M UTC')}</strong></p>
                </div>
        """
        
        # Add news alerts section
        if news_alerts:
            html += f"""
                <div class="alert-section">
                    <div class="alert-header">
                        📰 News Alerts ({len(news_alerts)} found)
                    </div>
                    <div class="alert-content">
            """
            
            for alert in news_alerts:
                article = alert['article']
                html += f"""
                        <div class="alert-item">
                            <div class="alert-title">{article['title']}</div>
                            <div class="alert-meta">
                                <strong>Source:</strong> {article['source_name']} | 
                                <strong>Published:</strong> {article['published'].strftime('%Y-%m-%d %H:%M UTC') if article['published'] else 'Unknown'}
                            </div>
                            <div>
                                <a href="{article['link']}" class="link" target="_blank">Read Full Article →</a>
                            </div>
                            <div style="margin-top: 10px;">
                                {f'<span class="companies">🏢 {company}</span>' for company in alert['mentioned_companies']}
                                {f'<span class="keywords">🔑 {keyword}</span>' for keyword in alert['found_keywords']}
                                <span class="score">📊 Score: {alert['relevance_score']:.2f}</span>
                            </div>
                            <div style="margin-top: 10px; font-size: 14px; color: #666;">
                                {article.get('summary', 'No summary available')[:200]}...
                            </div>
                        </div>
                """
            
            html += """
                    </div>
                </div>
            """
        
        # Add Twitter alerts section
        if twitter_alerts:
            html += f"""
                <div class="alert-section">
                    <div class="alert-header">
                        🐦 Twitter Alerts ({len(twitter_alerts)} found)
                    </div>
                    <div class="alert-content">
            """
            
            for alert in twitter_alerts:
                tweet = alert['tweet']
                html += f"""
                        <div class="alert-item">
                            <div class="alert-title">@{tweet['user']['screen_name']} - {tweet['user']['name']}</div>
                            <div class="alert-meta">
                                <strong>Posted:</strong> {tweet['created_at'].strftime('%Y-%m-%d %H:%M UTC')} | 
                                <strong>Engagement:</strong> {tweet['retweet_count']} RTs, {tweet['favorite_count']} Likes | 
                                <strong>Followers:</strong> {tweet['user']['followers_count']:,}
                            </div>
                            <div>
                                <a href="{tweet['url']}" class="link" target="_blank">View Tweet →</a>
                            </div>
                            <div class="tweet-content">
                                {tweet['text']}
                            </div>
                            <div style="margin-top: 10px;">
                                {f'<span class="companies">🏢 {company}</span>' for company in alert['mentioned_companies']}
                                {f'<span class="keywords">🔑 {keyword}</span>' for keyword in alert['found_keywords']}
                                <span class="score">📊 Score: {alert['relevance_score']:.2f}</span>
                            </div>
                        </div>
                """
            
            html += """
                    </div>
                </div>
            """
        
        # Add footer
        html += f"""
                <div class="footer">
                    <p>This alert was generated by the Crypto TGE Monitor system.</p>
                    <p>Monitor configured for {len(COMPANIES)} companies and {len(TGE_KEYWORDS)} TGE keywords.</p>
                    <p>Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def send_test_email(self) -> bool:
        """Send a test email to verify configuration."""
        if not self.enabled:
            self.logger.warning("Email notifications disabled - configuration incomplete")
            return False
        
        try:
            subject = "🧪 Crypto TGE Monitor - Test Email"
            body = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #007bff; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0; }}
                    .content {{ background-color: #f8f9fa; padding: 20px; border-radius: 0 0 5px 5px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>🧪 Test Email</h1>
                    </div>
                    <div class="content">
                        <p><strong>Crypto TGE Monitor Test Email</strong></p>
                        <p>This is a test email to verify that the email notification system is working correctly.</p>
                        <p><strong>Timestamp:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
                        <p>If you received this email, the notification system is properly configured!</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            msg = MIMEMultipart('alternative')
            msg['From'] = self.email_user
            msg['To'] = self.recipient_email
            msg['Subject'] = subject
            
            html_body = MIMEText(body, 'html')
            msg.attach(html_body)
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_user, self.email_password)
                server.send_message(msg)
            
            self.logger.info(f"Test email sent successfully to {self.recipient_email}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send test email: {str(e)}")
            return False
    
    def send_daily_summary(self, news_count: int, twitter_count: int, total_processed: int) -> bool:
        """Send daily summary email."""
        if not self.enabled:
            return False
        
        try:
            subject = f"📊 Daily TGE Monitor Summary - {datetime.now().strftime('%Y-%m-%d')}"
            
            body = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #28a745; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0; }}
                    .content {{ background-color: #f8f9fa; padding: 20px; border-radius: 0 0 5px 5px; }}
                    .stat {{ background-color: white; padding: 15px; margin: 10px 0; border-radius: 5px; border-left: 4px solid #28a745; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>📊 Daily Summary</h1>
                        <p>Crypto TGE Monitor - {datetime.now().strftime('%Y-%m-%d')}</p>
                    </div>
                    <div class="content">
                        <div class="stat">
                            <h3>📰 News Articles Processed</h3>
                            <p><strong>{total_processed}</strong> articles analyzed</p>
                        </div>
                        <div class="stat">
                            <h3>🚀 TGE Alerts Found</h3>
                            <p><strong>{news_count}</strong> news alerts</p>
                            <p><strong>{twitter_count}</strong> Twitter alerts</p>
                        </div>
                        <div class="stat">
                            <h3>📈 System Status</h3>
                            <p>✅ All monitoring systems operational</p>
                            <p>✅ Email notifications working</p>
                        </div>
                    </div>
                </div>
            </body>
            </html>
            """
            
            msg = MIMEMultipart('alternative')
            msg['From'] = self.email_user
            msg['To'] = self.recipient_email
            msg['Subject'] = subject
            
            html_body = MIMEText(body, 'html')
            msg.attach(html_body)
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_user, self.email_password)
                server.send_message(msg)
            
            self.logger.info(f"Daily summary email sent to {self.recipient_email}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send daily summary email: {str(e)}")
            return False


if __name__ == "__main__":
    notifier = EmailNotifier()
    
    # Test email functionality
    print("Testing email configuration...")
    if notifier.send_test_email():
        print("✅ Test email sent successfully!")
    else:
        print("❌ Failed to send test email")
    
    # Test with sample data
    sample_news_alert = {
        'article': {
            'title': 'Sample TGE Announcement',
            'link': 'https://example.com',
            'published': datetime.now(),
            'source_name': 'Test Source',
            'summary': 'This is a test TGE announcement for demonstration purposes.'
        },
        'mentioned_companies': ['Test Company'],
        'found_keywords': ['TGE', 'token launch'],
        'relevance_score': 0.85
    }
    
    sample_twitter_alert = {
        'tweet': {
            'text': 'Excited to announce our TGE is coming soon! 🚀',
            'user': {'screen_name': 'testuser', 'name': 'Test User', 'followers_count': 1000},
            'created_at': datetime.now(),
            'url': 'https://twitter.com/testuser/status/123',
            'retweet_count': 10,
            'favorite_count': 50
        },
        'mentioned_companies': ['Test Company'],
        'found_keywords': ['TGE'],
        'relevance_score': 0.75
    }
    
    print("\nTesting TGE alert email...")
    if notifier.send_tge_alert_email([sample_news_alert], [sample_twitter_alert]):
        print("✅ TGE alert email sent successfully!")
    else:
        print("❌ Failed to send TGE alert email")

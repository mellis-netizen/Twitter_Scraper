"""
Email Notification System for Crypto TGE Alerts
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from typing import List, Dict, Optional

from config import EMAIL_CONFIG, COMPANIES, TGE_KEYWORDS  # COMPANIES/KEYWORDS used in footer


class EmailNotifier:
    """Class for sending email notifications about TGE events."""

    def __init__(self):
        self.setup_logging()
        self.smtp_server = EMAIL_CONFIG.get('smtp_server')
        self.smtp_port = EMAIL_CONFIG.get('smtp_port')
        self.email_user = EMAIL_CONFIG.get('email_user')
        self.email_password = EMAIL_CONFIG.get('email_password')
        self.recipient_email = EMAIL_CONFIG.get('recipient_email')

        # Check if email is configured
        if not all([self.smtp_server, self.smtp_port, self.email_user, self.email_password, self.recipient_email]):
            self.logger.warning("Email configuration incomplete. Email notifications will be disabled.")
            self.enabled = False
        else:
            self.enabled = True

    def setup_logging(self):
        """Setup logging configuration."""
        self.logger = logging.getLogger("email_notifier")

    # -------------------------
    # Low-level send helper (with detailed SMTP logging)
    # -------------------------
    def _send_email(self, subject: str, html: str, text: Optional[str] = None) -> bool:
        if not self.enabled:
            self.logger.warning("Email notifications disabled - configuration incomplete")
            return False

        # Build MIME message (HTML + optional plain text)
        msg = MIMEMultipart('alternative')
        msg['From'] = self.email_user
        msg['To'] = self.recipient_email
        msg['Subject'] = subject
        if text:
            msg.attach(MIMEText(text, 'plain', 'utf-8'))
        msg.attach(MIMEText(html, 'html', 'utf-8'))

        try:
            use_ssl = str(self.smtp_port) == "465"
            if use_ssl:
                server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, timeout=20)
            else:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=20)

            try:
                # Enable verbose SMTP transcript in logs
                server.set_debuglevel(1)
                self.logger.info("Connecting to SMTP %s:%s (SSL=%s)", self.smtp_server, self.smtp_port, use_ssl)

                # EHLO before auth (and before STARTTLS on 587)
                code, hello = server.ehlo()
                self.logger.info("SMTP EHLO: %s %s", code, hello)

                if not use_ssl:
                    # 587 path: STARTTLS upgrade
                    code, resp = server.starttls()
                    self.logger.info("SMTP STARTTLS: %s %s", code, resp)
                    code, hello2 = server.ehlo()
                    self.logger.info("SMTP EHLO (post-TLS): %s %s", code, hello2)

                # Login
                server.login(self.email_user, self.email_password)
                self.logger.info("SMTP login OK for %s", self.email_user)

                # Support multiple recipients separated by commas
                from_addr = self.email_user
                to_addrs = [a.strip() for a in self.recipient_email.split(",") if a.strip()]

                # Use sendmail so we can inspect refused recipients
                refused = server.sendmail(from_addr, to_addrs, msg.as_string())

                if refused:
                    # Dict of {recipient: (code, resp)} for failures
                    self.logger.error("SMTP refused recipients: %s", refused)
                    return False

                self.logger.info("Email accepted by SMTP server for: %s", to_addrs)
                return True

            finally:
                try:
                    server.quit()
                except Exception:
                    server.close()

        except smtplib.SMTPAuthenticationError as e:
            self.logger.error("SMTP authentication failed: %s", e, exc_info=True)
            return False
        except smtplib.SMTPRecipientsRefused as e:
            self.logger.error("All recipients refused: %s", getattr(e, "recipients", {}), exc_info=True)
            return False
        except smtplib.SMTPException as e:
            self.logger.error("SMTP error: %s", e, exc_info=True)
            return False
        except Exception as e:
            self.logger.error("Unexpected error sending email: %s", e, exc_info=True)
            return False

    # -------------------------
    # Public API
    # -------------------------
    def send_tge_alert_email(
        self,
        news_alerts: List[Dict],
        twitter_alerts: List[Dict],
        meta: Optional[Dict] = None,
    ) -> bool:
        """Send email with TGE alerts from news and Twitter."""
        if not self.enabled:
            self.logger.warning("Email notifications disabled - configuration incomplete")
            return False

        # Even if there are no alerts, return True (pipeline shouldn’t error on “nothing found”)
        if not news_alerts and not twitter_alerts:
            self.logger.info("No TGE alerts to send")
            return True

        meta = meta or {}
        subject = self._generate_email_subject(news_alerts, twitter_alerts, meta)
        body = self._generate_email_body(news_alerts, twitter_alerts, meta)
        return self._send_email(subject, body)

    def send_test_email(self) -> bool:
        """
        Lightweight test used by test_components().
        Sends a small HTML test so the full SMTP path is exercised.
        """
        if not self.enabled:
            self.logger.warning("Email notifications disabled - cannot send test email.")
            return False

        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        subject = "🧪 Crypto TGE Monitor — Test Email"
        html = f"""
        <html><body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
            <h2>✅ Crypto TGE Monitor — Test Email</h2>
            <p>This is a connectivity test from the monitor.</p>
            <p><strong>Time:</strong> {ts}</p>
        </body></html>
        """
        return self._send_email(subject, html, f"Crypto TGE Monitor test at {ts}")

    def send_daily_summary(self, news_count: int, twitter_count: int, total_processed: int) -> bool:
        """Send daily summary email."""
        if not self.enabled:
            return False
        try:
            subject = f"📊 Daily TGE Monitor Summary - {datetime.now().strftime('%Y-%m-%d')}"
            html = f"""
            <!DOCTYPE html>
            <html>
            <head><meta charset="UTF-8"></head>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width:600px;margin:0 auto;padding:20px;">
                    <h2>📊 Daily Summary — {datetime.now().strftime('%Y-%m-%d')}</h2>
                    <ul>
                        <li><strong>Total processed</strong>: {total_processed}</li>
                        <li><strong>News alerts</strong>: {news_count}</li>
                        <li><strong>Twitter alerts</strong>: {twitter_count}</li>
                    </ul>
                </div>
            </body>
            </html>
            """
            return self._send_email(subject, html)
        except Exception as e:
            self.logger.error("Failed to send daily summary email: %s", e, exc_info=True)
            return False

    # -------------------------
    # Rendering helpers
    # -------------------------
    def _generate_email_subject(
        self,
        news_alerts: List[Dict],
        twitter_alerts: List[Dict],
        meta: Dict
    ) -> str:
        total = len(news_alerts) + len(twitter_alerts)
        rl = " (partial, rate-limited)" if meta.get("twitter_rate_limited") else ""
        if total == 0:
            return f"Crypto TGE Monitor — No alerts{rl}"
        if total == 1:
            src = (news_alerts or twitter_alerts)[0]
            companies = src.get("mentioned_companies") or []
            label = companies[0] if companies else "Unknown"
            return f"🚀 TGE Alert: {label}{rl}"
        return f"🚀 {total} TGE Alerts Detected{rl} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    def _news_item_from_alert(self, alert: Dict) -> Dict:
        """
        Normalize both shapes:
        - flat: {'title','link','summary','published','source',...}
        - nested: {'article': {...}, ...}
        """
        if "article" in alert and isinstance(alert["article"], dict):
            art = alert["article"]
            return {
                "title": art.get("title"),
                "link": art.get("link"),
                "summary": art.get("summary"),
                "published": art.get("published"),
                "source_name": art.get("source_name") or alert.get("source") or "",
            }
        # flat
        return {
            "title": alert.get("title"),
            "link": alert.get("link"),
            "summary": alert.get("summary"),
            "published": alert.get("published"),
            "source_name": alert.get("source") or "",
        }

    def _generate_email_body(
        self,
        news_alerts: List[Dict],
        twitter_alerts: List[Dict],
        meta: Dict
    ) -> str:
        ts = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
        rl_banner = ""
        if meta.get("twitter_rate_limited"):
            rl_banner = (
                '<div style="background:#fff3cd;border:1px solid #ffeeba;padding:10px;'
                'border-radius:6px;margin-bottom:16px;">'
                '⚠️ Twitter/API rate limiting detected this cycle — results may be partial.'
                '</div>'
            )

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
                .header {{ text-align: center; border-bottom: 3px solid #007bff; padding-bottom: 20px; margin-bottom: 20px; }}
                .alert-section {{ margin-bottom: 30px; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden; }}
                .alert-header {{ background-color: #007bff; color: white; padding: 12px 16px; font-weight: bold; font-size: 16px; }}
                .alert-content {{ padding: 16px; }}
                .alert-item {{ border-bottom: 1px solid #f0f0f0; padding: 14px 0; }}
                .alert-item:last-child {{ border-bottom: none; }}
                .alert-title {{ font-size: 15px; font-weight: 600; color: #007bff; margin-bottom: 6px; }}
                .alert-meta {{ font-size: 13px; color: #666; margin-bottom: 8px; }}
                .companies, .keywords, .score {{
                    padding: 6px 10px; border-radius: 5px; margin: 3px 4px 0 0; display: inline-block;
                }}
                .companies {{ background-color: #e8f4fd; }}
                .keywords  {{ background-color: #fff3cd; }}
                .score     {{ background-color: #d4edda; font-weight: 600; }}
                .tweet-content {{ background:#f8f9fa; padding: 12px; border-radius: 5px; border-left: 4px solid #007bff; margin: 8px 0; font-style: italic; }}
                .footer {{ text-align: center; margin-top: 20px; padding-top: 12px; border-top: 1px solid #e0e0e0; color: #666; font-size: 12px; }}
                .link {{ color: #007bff; text-decoration: none; }}
                .link:hover {{ text-decoration: underline; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🚀 Crypto TGE Monitor Alert</h1>
                    <p>Token Generation Event Detection Report</p>
                    <p><strong>{ts}</strong></p>
                    {rl_banner}
                </div>
        """

        # News section
        if news_alerts:
            html += f"""
                <div class="alert-section">
                    <div class="alert-header">📰 News Alerts ({len(news_alerts)} found)</div>
                    <div class="alert-content">
            """
            for alert in news_alerts:
                art = self._news_item_from_alert(alert)
                pubs = art.get('published')
                if isinstance(pubs, datetime):
                    try:
                        if pubs.tzinfo is None:
                            pubs = pubs.replace(tzinfo=timezone.utc)
                        pub_str = pubs.strftime('%Y-%m-%d %H:%M UTC')
                    except Exception:
                        pub_str = str(pubs)
                else:
                    pub_str = 'Unknown'

                comps = ''.join(f'<span class="companies">🏢 {c}</span>'
                                for c in sorted(alert.get('mentioned_companies', [])))
                keys  = ''.join(f'<span class="keywords">🔑 {k}</span>'
                                for k in sorted(alert.get('found_keywords', [])))
                score = f'<span class="score">📊 Score: {alert.get("relevance_score", 0):.2f}</span>'

                html += f"""
                        <div class="alert-item">
                            <div class="alert-title">{(art.get('title') or 'Untitled')}</div>
                            <div class="alert-meta">
                                <strong>Source:</strong> {art.get('source_name','')} |
                                <strong>Published:</strong> {pub_str}
                            </div>
                            <div><a href="{art.get('link') or '#'}" class="link" target="_blank">Read Full Article →</a></div>
                            <div style="margin-top: 8px;">{comps}{keys}{score}</div>
                            <div style="margin-top: 8px; font-size: 14px; color: #666;">
                                {(art.get('summary') or 'No summary available')[:200]}...
                            </div>
                        </div>
                """
            html += "</div></div>"

        # Twitter section
        if twitter_alerts:
            html += f"""
                <div class="alert-section">
                    <div class="alert-header">🐦 Twitter Alerts ({len(twitter_alerts)} found)</div>
                    <div class="alert-content">
            """
            for alert in twitter_alerts:
                tweet = alert.get('tweet', {})
                ts_t = tweet.get('created_at')
                if isinstance(ts_t, datetime):
                    try:
                        if ts_t.tzinfo is None:
                            ts_t = ts_t.replace(tzinfo=timezone.utc)
                        ts_str = ts_t.strftime('%Y-%m-%d %H:%M UTC')
                    except Exception:
                        ts_str = str(ts_t)
                else:
                    ts_str = 'Unknown'

                comps = ''.join(f'<span class="companies">🏢 {c}</span>'
                                for c in sorted(alert.get('mentioned_companies', [])))
                keys  = ''.join(f'<span class="keywords">🔑 {k}</span>'
                                for k in sorted(alert.get('found_keywords', [])))
                score = f'<span class="score">📊 Score: {alert.get("relevance_score", 0):.2f}</span>'

                html += f"""
                        <div class="alert-item">
                            <div class="alert-title">@{tweet.get('user',{}).get('screen_name','unknown')} - {tweet.get('user',{}).get('name','Unknown')}</div>
                            <div class="alert-meta">
                                <strong>Posted:</strong> {ts_str} |
                                <strong>Engagement:</strong> {tweet.get('retweet_count',0)} RTs, {tweet.get('favorite_count',0)} Likes |
                                <strong>Followers:</strong> {tweet.get('user',{}).get('followers_count',0):,}
                            </div>
                            <div><a href="{tweet.get('url') or '#'}" class="link" target="_blank">View Tweet →</a></div>
                            <div class="tweet-content">{tweet.get('text','')}</div>
                            <div style="margin-top: 8px;">{comps}{keys}{score}</div>
                        </div>
                """
            html += "</div></div>"

        # Footer
        html += f"""
                <div class="footer">
                    <p>This alert was generated by the Crypto TGE Monitor system.</p>
                    <p>Monitor configured for {len(COMPANIES)} companies and {len(TGE_KEYWORDS)} TGE keywords.</p>
                    <p>Last updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
                </div>
            </div>
        </body>
        </html>
        """
        return html

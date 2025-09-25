import os
import logging
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration validation
def validate_config() -> Dict[str, bool]:
    """Validate configuration and return status of each component."""
    validation_results = {
        'email_config': False,
        'twitter_config': False,
        'logging_config': False,
        'companies_config': False,
        'sources_config': False,
        'keywords_config': False,
        'urls_config': False
    }
    
    # Validate email configuration
    try:
        email_required = ['EMAIL_USER', 'EMAIL_PASSWORD', 'RECIPIENT_EMAIL']
        email_optional = ['SMTP_SERVER', 'SMTP_PORT']
        
        # Check required fields
        if all(os.getenv(field) for field in email_required):
            validation_results['email_config'] = True
        else:
            logging.warning("Email configuration incomplete - some required fields missing")
    except Exception as e:
        logging.error(f"Email configuration validation failed: {str(e)}")
    
    # Validate Twitter configuration (Bearer token only for API v2)
    try:
        bearer_token = os.getenv('TWITTER_BEARER_TOKEN')

        # Twitter is optional, but if bearer token is provided, validate it
        if bearer_token:
            # Basic validation for bearer token format
            if len(bearer_token.strip()) >= 40 and not any(placeholder in bearer_token.lower()
                                                          for placeholder in ['your_bearer_token', 'placeholder', 'test', 'example']):
                validation_results['twitter_config'] = True
            else:
                logging.warning("Twitter bearer token appears to be invalid")
                validation_results['twitter_config'] = False
        else:
            validation_results['twitter_config'] = True  # No Twitter config is valid
    except Exception as e:
        logging.error(f"Twitter configuration validation failed: {str(e)}")
    
    # Validate logging configuration
    try:
        log_level = os.getenv('LOG_LEVEL', 'INFO')
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if log_level.upper() in valid_levels:
            validation_results['logging_config'] = True
        else:
            logging.warning(f"Invalid log level: {log_level}")
    except Exception as e:
        logging.error(f"Logging configuration validation failed: {str(e)}")
    
    # Validate companies configuration
    try:
        if COMPANIES and len(COMPANIES) > 0:
            validation_results['companies_config'] = True
        else:
            logging.warning("No companies configured for monitoring")
    except Exception as e:
        logging.error(f"Companies configuration validation failed: {str(e)}")
    
    # Validate sources configuration
    try:
        if NEWS_SOURCES and len(NEWS_SOURCES) > 0:
            validation_results['sources_config'] = True
        else:
            logging.warning("No news sources configured for monitoring")
    except Exception as e:
        logging.error(f"Sources configuration validation failed: {str(e)}")
    
    # Validate keywords configuration
    try:
        if TGE_KEYWORDS and len(TGE_KEYWORDS) > 0:
            # Check for empty or invalid keywords
            valid_keywords = [k for k in TGE_KEYWORDS if k and isinstance(k, str) and len(k.strip()) > 0]
            if len(valid_keywords) == len(TGE_KEYWORDS):
                validation_results['keywords_config'] = True
            else:
                logging.warning("Some TGE keywords are invalid or empty")
        else:
            logging.warning("No TGE keywords configured")
    except Exception as e:
        logging.error(f"Keywords configuration validation failed: {str(e)}")
    
    # Validate URLs configuration
    try:
        from urllib.parse import urlparse
        valid_urls = 0
        for url in NEWS_SOURCES:
            try:
                parsed = urlparse(url)
                if parsed.scheme in ['http', 'https'] and parsed.netloc:
                    valid_urls += 1
            except Exception:
                logging.warning(f"Invalid URL in sources: {url}")
        
        if valid_urls > 0:
            validation_results['urls_config'] = True
            logging.info(f"Validated {valid_urls}/{len(NEWS_SOURCES)} news source URLs")
        else:
            logging.error("No valid URLs found in news sources")
    except Exception as e:
        logging.error(f"URL validation failed: {str(e)}")
    
    return validation_results

# Companies to monitor (with aliases and token symbols for precise matching)
COMPANIES = [
    {"name": "Corn", "aliases": ["Corn Protocol", "Corn Finance"], "tokens": ["CORN"], "exclusions": ["popcorn", "corn futures", "corn price"]},
    {"name": "Curvance", "aliases": ["Curvance Finance", "Curvance Protocol"], "tokens": ["CRV", "CURV"], "exclusions": []},
    {"name": "Darkbright", "aliases": ["Darkbright Labs", "Darkbright Protocol"], "tokens": [], "exclusions": []},
    {"name": "Fabric", "aliases": ["Fabric Protocol", "Fabric Labs", "Fabric Cryptography"], "tokens": ["FAB"], "exclusions": ["fabric softener", "textile fabric", "fabric store"]},
    {"name": "Caldera", "aliases": ["Caldera Labs", "Caldera Protocol", "Caldera Chain"], "tokens": ["CAL"], "exclusions": ["volcanic caldera", "yellowstone caldera"]},
    {"name": "Open Eden", "aliases": ["OpenEden", "Open Eden Protocol"], "tokens": ["TBILL"], "exclusions": []},
    {"name": "XAI", "aliases": ["XAI Games", "Xai", "Xai Games"], "tokens": ["XAI"], "exclusions": ["explainable ai", "xai technology"]},
    {"name": "Espresso", "aliases": ["Espresso Systems", "Espresso Labs"], "tokens": ["ESPR"], "exclusions": ["coffee", "espresso machine", "starbucks"]},
    {"name": "Clique", "aliases": ["Clique Protocol", "Clique Labs"], "tokens": ["CLI"], "exclusions": ["social clique", "clique theory"]},
    {"name": "TreasureDAO", "aliases": ["Treasure DAO", "Treasure", "Treasure Protocol"], "tokens": ["MAGIC"], "exclusions": ["treasure hunt", "national treasure"]},
    {"name": "Camelot", "aliases": ["Camelot DEX", "Camelot Protocol"], "tokens": ["GRAIL"], "exclusions": ["king arthur", "camelot movie"]},
    {"name": "DuckChain", "aliases": ["Duck Chain", "DuckChain Protocol"], "tokens": ["DUCK"], "exclusions": ["rubber duck", "donald duck"]},
    {"name": "Spacecoin", "aliases": ["Space Coin", "Spacecoin Protocol"], "tokens": ["SPACE"], "exclusions": ["nasa", "space exploration"]},
    {"name": "Fhenix", "aliases": ["Fhenix Token", "Fhenix Protocol"], "tokens": ["FHE"], "exclusions": []},
    {"name": "USD.ai", "aliases": ["USDai", "USD AI", "USD.ai Protocol"], "tokens": ["USDAI"], "exclusions": []},
    {"name": "Huddle01", "aliases": ["Huddle 01", "Huddle01 Protocol"], "tokens": ["HUD"], "exclusions": ["football huddle", "team huddle"]},
    {"name": "Succinct", "aliases": ["Succinct Labs", "Succinct Protocol"], "tokens": ["SUC"], "exclusions": ["succinct definition", "succinct writing"]}
]

# TGE-related keywords - categorized by confidence level
# High confidence keywords (strong TGE indicators)
HIGH_CONFIDENCE_TGE_KEYWORDS = [
    "TGE", "token generation event", "token launch", "token release",
    "token distribution", "airdrop", "token sale", "ICO", "IDO",
    "token listing", "token launch date", "token generation",
    "token deployment", "token goes live", "token trading launch",
    "token presale", "token public sale", "governance token launch",
    "utility token launch", "mainnet token launch"
]

# Medium confidence keywords (require company context)
MEDIUM_CONFIDENCE_TGE_KEYWORDS = [
    "mainnet launch", "mainnet release", "mainnet deployment",
    "protocol launch", "network launch", "platform launch",
    "token minting", "token creation", "token unlock",
    "token emission", "tokenomics", "token economics",
    "launching", "going live", "live on mainnet"
]

# Low confidence keywords (require company + multiple indicators)
LOW_CONFIDENCE_TGE_KEYWORDS = [
    "announce", "announced", "announcing", "announcement",
    "releasing", "deploying", "coming soon", "launch date",
    "release date", "go live", "available on", "trading on", "listed on"
]

# Combined list for backward compatibility
TGE_KEYWORDS = HIGH_CONFIDENCE_TGE_KEYWORDS + MEDIUM_CONFIDENCE_TGE_KEYWORDS + LOW_CONFIDENCE_TGE_KEYWORDS

# Crypto news sources (EVM-focused; removed bitcoin-only outlets)
NEWS_SOURCES = [
    # General crypto with strong EVM/DeFi coverage
    "https://decrypt.co/feed",
    "https://www.theblock.co/rss.xml",
    "https://www.coindesk.com/arc/outboundfeeds/rss",
        
    # DeFi / EVM native outlets
    "https://thedefiant.io/feed",  # The Defiant
    "https://www.bankless.com/feed", 
    "https://cryptobriefing.com/feed",
    "https://cointelegraph.com/rss",
    "https://zycrypto.com/feed/",
    "https://www.cryptocurrencyscript.com/blog/feed",
    "https://e-cryptonews.com/feed/",
    "https://coinidol.com/rss2/",
    "https://zebpay.com/feed",
    "https://coincheckup.com/blog/feed/",
    "https://bitcoinethereumnews.com/feed/",
    "https://u.today/rss.php",
    "https://blockchain.news/rss",
    "https://currencycrypt.net/feed/",
    "https://coingeek.com/feed/",
    "https://cryptoadventure.com/feed/",
    "https://www.cryptobreaking.com/feed/",
    "https://ambcrypto.com/feed/",
    "https://www.platinumcryptoacademy.com/feed/",
    "https://www.cryptela.com/blog-rss",
    "https://decrypt.co/feed",
    "https://moonwhale.io/feed/",
    "https://moralis.com/blog/feed/",
    "https://cryptobullsclub.com/feed/",
    "https://robokoin.com/feed/",
    "https://www.cryptomaton.org/feed/",
    "https://www.trustnodes.com/feed",
    "https://blog.bitmex.com/feed/",
    "https://fullycrypto.com/feed",
    "https://coindoo.com/feed/",
    "https://dailycoin.com/feed/",
    "https://blockonomi.com/feed/",
    "https://blocknewsmedia.com/feed/",
    "https://cryptopurview.com/feed/",
    "https://www.talkcrypto.org/blog/feed/",
    "https://thenewscrypto.com/feed/",
    "https://blog.latoken.com/feed",
    "https://coinlabz.com/feed/",
    "https://walletinvestor.com/blog/feed/",
    "https://tradecrypto.com/feed/",
    "https://crypto-economy.com/feed/",
    "https://nulltx.com/feed/",
    "https://cryptoworldseo.com/feed/",
    "https://vestorportal.com/rss/",
    "https://coingape.com/feed/",
    "https://cryptocurrencynews.com/feed/",
    "https://www.cryptoninjas.net/feed/",
    "https://blog.cex.io/feed",
    "https://cryptoshrypto.com/feed/",
    "https://www.cryptonewsz.com/feed/",
    "https://coinchapter.com/feed/",
    "https://thecryptobasic.com/feed/",
    "https://webscrypto.com/feed/",
    "https://bitpinas.com/feed/",
    "https://cryptoexchange4u.com/feed/",
    "https://allincrypto.com/feed/",
    "https://coincentral.com/news/feed/",
    "https://coinstats.app/blog/feed/",
    "https://coinpedia.org/feed/",
    "https://cryptonews.com/news/feed/",
    "https://multicoin.capital/rss.xml",
    "https://cryptodaily.co.uk/feed",
    "https://cryptonews.com.au/feed/",
    "https://medium.com/feed/coinmonks",
    "https://blog.bitfinex.com/feed/",
    "https://themarketscompass.substack.com/feed",
    "https://www.thecoinspost.com/feed/",
    "https://crypto.news/feed/",
    "https://cryptopotato.com/feed/",
    "https://www.dlnews.com/arc/outboundfeeds/rss/",    
    # Network ecosystem blogs (major EVM L1/L2s)
    "https://blog.ethereum.org/en/feed.xml",
    "https://arbitrumfoundation.medium.com/feed",  # Arbitrum Foundation (Medium)
    "https://medium.com/avalancheavax",
    "https://coinjournal.net/feed/",
    "https://avalancheavax.medium.com",
    "https://blog.fantom.foundation/rss/",
    "https://blog.cronos.org/feed/",  # Cronos
    "https://medium.com/feed/@CeloOrg",  # Celo
    "https://medium.com/feed/@AstarNetwork",  # Astar
]
# Company Twitter handles (verified and researched)
COMPANY_TWITTERS = {
    # Project/company accounts
    "Corn": None,  # No official Twitter found
    "Corn2": None,  # No official Twitter found
    "Curvance": "@CurvanceFinance",
    "Darkbright": None,  # No official Twitter found
    "Fabric": "@fabric_xyz",
    "Caldera": "@CalderaXYZ",
    "Open Eden": "@OpenEden_HQ",
    "XAI": "@XaiGames",
    "Espresso": "@EspressoSys",
    "2046 Angels Ltd": None,  # No official Twitter found
    "Clique": None,  # No official Twitter found
    "TreasureDAO": "@Treasure_DAO",
    "Camelot": "@CamelotDEX",
    "DuckChain": None,  # No official Twitter found
    "Spacecoin": None,  # No official Twitter found
    "FhenixToken": "@FhenixIO",
    "USD.ai": None,  # No official Twitter found
    "Huddle01": "@huddle01",
    "Succinct": "@SuccinctLabs",
}

# Core crypto/EVM news accounts to monitor (complementary to company handles)
CORE_NEWS_TWITTERS = [
    # Major crypto news outlets
    "@decryptmedia",
    "@CoinDesk",
    "@TheBlock__",
    "@DefiantNews",
    "@BanklessHQ",
    "@DLNewsInfo",
    "@cz_binance",
    "@WatcherGuru",
    "@willclemente",
    "@MessariCrypto",
    "@WuBlockchain",
    "@a16zcrypto",
    "@AltcoinDailyio",
    "@AltcoinGordon",
    "@IncomeSharks",
    "@ThatMartiniGuy",
    "@TheDefiant",
    "@CoinList",
    "@tokenfi",
    "@TheCryptoLark",
    "@Ignasdefi",
    "@HashLock_",
    "@CryptoSlate",
    "@Blockworks_",
    "@Foresight_News",
    "@Cointelegraph",
    "@Delphi_Digital",
    "@paradigm",
    "@PanteraCapital",
    "@multicoincap",
    "@cdixon",
    "@packyM",
    "@DefiLlama",
    "@BanklessHQ",
    "@MoonOverlord",
    "@HaskaTrades",
    "@milesdeutscher",
    
    # EVM ecosystem accounts
    "@ethereum",
    "@VitalikButerin",
    "@ethdotorg",
    "@0xPolygon",
    "@arbitrum",
    "@optimismPBC",
    "@avax",
    "@FantomFDN",
    "@cronos_chain",
    "@harmonyprotocol",
    "@MoonbeamNetwork",
    "@klaytn_official",
    "@CeloOrg",
    "@AstarNetwork",
    "@MetisDAO",
    "@syscoin",
    "@HelloTelos",
    
    # DeFi and Web3 influencers
    "@PatrickAlphaC",
    "@VittoStack",
    "@thatguyintech",
    "@iam_preethi",
    "@dabit3",
    "@oliverjumpertz",
    "@austingriffith",
    "@sandeepnailwal",
    "@el33th4xor",
    "@michaelfkong",
    "@OffchainLabs",
    "@kelvinfichter",
]

# Derived list of Twitter accounts to monitor
TWITTER_ACCOUNTS = [
    handle for handle in (
        list({h for h in COMPANY_TWITTERS.values() if h}) + CORE_NEWS_TWITTERS
    )
]

# Email configuration
EMAIL_CONFIG = {
    'smtp_server': os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
    'smtp_port': int(os.getenv('SMTP_PORT', 587)),
    'email_user': os.getenv('EMAIL_USER'),
    'email_password': os.getenv('EMAIL_PASSWORD'),
    'recipient_email': os.getenv('RECIPIENT_EMAIL', 'mellis@offchainlabs.com')
}

# Twitter API configuration (Bearer token only for API v2)
TWITTER_CONFIG = {
    'bearer_token': os.getenv('TWITTER_BEARER_TOKEN')
}

# Logging configuration
LOG_CONFIG = {
    'level': os.getenv('LOG_LEVEL', 'INFO'),
    'file': os.getenv('LOG_FILE', 'logs/crypto_monitor.log')
}


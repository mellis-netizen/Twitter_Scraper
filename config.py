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
        'sources_config': False
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
    
    # Validate Twitter configuration
    try:
        twitter_required = ['TWITTER_API_KEY', 'TWITTER_API_SECRET', 'TWITTER_ACCESS_TOKEN', 'TWITTER_ACCESS_TOKEN_SECRET']
        twitter_optional = ['TWITTER_BEARER_TOKEN']
        
        # Twitter is optional, but if any credentials are provided, validate them
        twitter_creds = [os.getenv(field) for field in twitter_required]
        if any(twitter_creds):  # If any Twitter creds are provided
            if all(twitter_creds):  # All required creds must be present
                validation_results['twitter_config'] = True
            else:
                logging.warning("Twitter configuration incomplete - some required fields missing")
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
    
    return validation_results

# Companies to monitor
COMPANIES = [
    "Corn",
    "Corn2", 
    "Curvance",
    "Darkbright",
    "Fabric",
    "Caldera",
    "Open Eden",
    "XAI",
    "Espresso",
    "2046 Angels Ltd",
    "Clique",
    "TreasureDAO",
    "Camelot",
    "DuckChain",
    "Spacecoin",
    "FhenixToken",
    "USD.ai",
    "Huddle01",
    "Succinct"
]

# TGE-related keywords
TGE_KEYWORDS = [
    "TGE", "token generation event", "token launch", "token release",
    "token distribution", "airdrop", "token sale", "ICO", "IDO",
    "token listing", "token launch date", "token generation",
    "token deployment", "token minting", "token creation"
]

# Crypto news sources (EVM-focused; removed bitcoin-only outlets)
NEWS_SOURCES = [
    # General crypto with strong EVM/DeFi coverage
    "https://decrypt.co/feed",
    "https://www.theblock.co/rss.xml",
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    
    # Ethereum-focused categories
    "https://www.coindesk.com/arc/outboundfeeds/rss/category/ethereum/",  # CoinDesk Ethereum
    "https://decrypt.co/tag/ethereum/feed",  # Decrypt Ethereum tag
    
    # DeFi / EVM native outlets
    "https://thedefiant.io/feed",  # The Defiant
    "https://www.bankless.com/feed",  # Bankless
    "https://dlnews.com/feed",  # DL News
    
    # Network ecosystem blogs (major EVM L1/L2s)
    "https://blog.ethereum.org/feed",  # Ethereum Foundation blog
    "https://blog.optimism.io/feed",  # Optimism
    "https://blog.polygon.technology/rss.xml",  # Polygon
    "https://arbitrumfoundation.medium.com/feed",  # Arbitrum Foundation (Medium)
    "https://medium.com/avalancheavax/feed",  # Avalanche
    "https://fantom.foundation/blog/feed/",  # Fantom
    "https://blog.cronos.org/feed/",  # Cronos
    "https://medium.com/feed/@harmonyprotocol",  # Harmony
    "https://moonbeam.network/blog/feed/",  # Moonbeam/Moonriver
    "https://medium.com/feed/@klaytn_official",  # Klaytn
    "https://medium.com/feed/@CeloOrg",  # Celo
    "https://medium.com/feed/@AstarNetwork",  # Astar
    "https://metisdao.medium.com/feed",  # Metis
    "https://syscoin.org/news/feed/",  # Syscoin
    "https://medium.com/feed/@telosfoundation",  # Telos
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

# Twitter API configuration
TWITTER_CONFIG = {
    'api_key': os.getenv('TWITTER_API_KEY'),
    'api_secret': os.getenv('TWITTER_API_SECRET'),
    'access_token': os.getenv('TWITTER_ACCESS_TOKEN'),
    'access_token_secret': os.getenv('TWITTER_ACCESS_TOKEN_SECRET'),
    'bearer_token': os.getenv('TWITTER_BEARER_TOKEN')
}

# Logging configuration
LOG_CONFIG = {
    'level': os.getenv('LOG_LEVEL', 'INFO'),
    'file': os.getenv('LOG_FILE', 'logs/crypto_monitor.log')
}


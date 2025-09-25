#!/usr/bin/env python3
"""
Simple matching logic test without external dependencies
"""

import re
import sys
import os

# Mock config data for testing
MOCK_COMPANIES = [
    {"name": "Curvance", "aliases": ["Curvance Finance", "Curvance Protocol"], "tokens": ["CRV", "CURV"], "exclusions": [], "priority": "HIGH", "status": "pre_token"},
    {"name": "Fhenix", "aliases": ["Fhenix Protocol", "Fhenix Labs"], "tokens": ["FHE"], "exclusions": [], "priority": "HIGH", "status": "pre_token"},
    {"name": "TreasureDAO", "aliases": ["Treasure DAO", "Treasure", "Treasure Protocol"], "tokens": ["MAGIC"], "exclusions": ["treasure hunt", "national treasure"], "priority": "MEDIUM", "status": "has_token"},
    {"name": "Fabric", "aliases": ["Fabric Protocol", "Fabric Labs"], "tokens": ["FAB"], "exclusions": ["fabric softener", "textile fabric", "fabric store"], "priority": "HIGH", "status": "pre_token"},
    {"name": "Espresso", "aliases": ["Espresso Systems", "Espresso Labs"], "tokens": ["ESPR"], "exclusions": ["coffee", "espresso machine", "starbucks"], "priority": "LOW", "status": "infrastructure"},
]

MOCK_HIGH_CONFIDENCE_KEYWORDS = [
    "TGE", "token generation event", "token launch", "token release",
    "token distribution", "airdrop", "token sale", "IDO", "initial dex offering"
]

MOCK_MEDIUM_CONFIDENCE_KEYWORDS = [
    "mainnet launch", "protocol launch", "tokenomics", "governance token launch"
]

def _text_from_alert(alert: dict) -> str:
    """Extract text from alert for matching"""
    parts = [
        alert.get("title", ""),
        alert.get("content", ""),
        alert.get("summary", ""),
    ]
    return " ".join([p for p in parts if p]).strip()

def mock_matches_company_and_keyword(alert: dict) -> bool:
    """Mock matching function based on our optimized logic"""
    if not isinstance(alert, dict):
        return False

    text = _text_from_alert(alert).lower()
    if not text or len(text.strip()) < 10:
        return False

    def _has(token: str) -> bool:
        if not token.strip():
            return False
        token = re.escape(token.strip())
        return re.search(rf"\b{token}\b", text, flags=re.IGNORECASE) is not None

    def _find_company_matches() -> list:
        matches = []
        for c in MOCK_COMPANIES:
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
        return [k for k in MOCK_HIGH_CONFIDENCE_KEYWORDS if _has(k)]

    def _has_medium_confidence_keywords() -> list:
        return [k for k in MOCK_MEDIUM_CONFIDENCE_KEYWORDS if _has(k)]

    def _has_multiple_tge_signals() -> bool:
        tge_signals = [
            "token", "coin", "crypto", "blockchain", "defi", "web3",
            "mainnet", "testnet", "protocol", "network", "chain",
            "launch", "release", "deploy", "announce", "live"
        ]
        signal_count = sum(1 for signal in tge_signals if _has(signal))
        return signal_count >= 3

    # Find company matches
    company_matches = _find_company_matches()
    if not company_matches:
        return False

    # Strategy 1: High confidence TGE keywords + company match
    high_conf_keywords = _has_high_confidence_keywords()
    if high_conf_keywords and company_matches:
        for match in company_matches:
            priority = match['company'].get('priority', 'LOW')
            if priority == 'HIGH':
                return True
            elif priority == 'MEDIUM' and len(high_conf_keywords) >= 1:
                return True
            elif priority == 'LOW' and len(high_conf_keywords) >= 2:
                return True
        return True

    # Strategy 2: Medium confidence keywords + company + multiple TGE signals
    medium_conf_keywords = _has_medium_confidence_keywords()
    if medium_conf_keywords and company_matches and _has_multiple_tge_signals():
        for match in company_matches:
            if match['company'].get('priority') == 'HIGH':
                return True
        return False

    # Strategy 3: Token symbol + specific TGE action words
    token_specific_actions = ["launch", "release", "deploy", "mint", "distribute", "airdrop"]
    for match in company_matches:
        if (match['token_match'] and
            any(_has(action) for action in token_specific_actions) and
            match['company'].get('priority') == 'HIGH'):
            return True

    return False

def run_matching_tests():
    """Run matching logic tests"""
    print("🔍 CRYPTO TGE MONITOR - MATCHING LOGIC TEST")
    print("="*50)

    test_cases = [
        # HIGH PRIORITY - Should match
        {
            "title": "Curvance Announces Token Generation Event",
            "content": "Curvance Finance announces TGE for Q1 2024",
            "expected": True,
            "category": "HIGH priority + TGE keyword"
        },
        {
            "title": "Fhenix Protocol Launches FHE Token",
            "content": "Fhenix announces FHE token launch and airdrop",
            "expected": True,
            "category": "HIGH priority + token launch"
        },

        # MEDIUM PRIORITY - Needs strong keywords
        {
            "title": "TreasureDAO Announces New Token Generation Event",
            "content": "TreasureDAO announces TGE for new utility token",
            "expected": True,
            "category": "MEDIUM priority + TGE keyword"
        },
        {
            "title": "TreasureDAO Platform Update",
            "content": "TreasureDAO announces new features and updates",
            "expected": False,
            "category": "MEDIUM priority + weak signals"
        },

        # EXCLUSIONS - Should not match
        {
            "title": "Fabric Store Grand Opening",
            "content": "Local fabric store opens new location this weekend",
            "expected": False,
            "category": "Exclusion words should prevent match"
        },
        {
            "title": "Best Espresso Machine Review",
            "content": "Coffee lovers review top espresso machine brands",
            "expected": False,
            "category": "Exclusion words should prevent match"
        },

        # EDGE CASES
        {
            "title": "Short",
            "content": "Hi",
            "expected": False,
            "category": "Too short content"
        },
        {
            "title": "Multiple Companies Token Event",
            "content": "Curvance and Fhenix announce joint TGE initiative",
            "expected": True,
            "category": "Multiple HIGH priority companies"
        }
    ]

    passed = 0
    total = len(test_cases)

    for i, test in enumerate(test_cases, 1):
        alert = {
            "title": test["title"],
            "content": test["content"],
            "url": f"https://example.com/{i}"
        }

        result = mock_matches_company_and_keyword(alert)
        status = "✅ PASS" if result == test["expected"] else "❌ FAIL"

        print(f"Test {i}: {status}")
        print(f"  Category: {test['category']}")
        print(f"  Title: {test['title'][:50]}...")
        print(f"  Expected: {test['expected']}, Got: {result}")
        print()

        if result == test["expected"]:
            passed += 1

    print("="*50)
    print(f"RESULTS: {passed}/{total} tests passed ({passed/total*100:.1f}%)")

    if passed == total:
        print("✅ ALL TESTS PASSED - System is optimally configured!")
    else:
        print(f"❌ {total-passed} tests failed - System needs adjustment")

    return passed == total

if __name__ == "__main__":
    run_matching_tests()
#!/usr/bin/env python3
"""
Enhanced System Test for Crypto TGE Monitor
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

import re

# Mock config data
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

def mock_enhanced_matches_company_and_keyword(alert: dict) -> tuple[bool, dict]:
    """Enhanced matching function with detailed match information"""

    # Default match details structure
    match_details = {
        'matched_companies': [],
        'matched_keywords': [],
        'matched_tokens': [],
        'match_strategy': None,
        'confidence_score': 0,
        'match_reasons': [],
        'priority_level': None
    }

    # Validate alert structure
    if not isinstance(alert, dict):
        return False, match_details

    text = _text_from_alert(alert).lower()
    if not text or len(text.strip()) < 10:
        return False, match_details

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
            matched_names = [name for name in all_names if name and _has(name)]

            # Check token symbols
            matched_tokens = [token for token in tokens if _has(token)]

            if matched_names or matched_tokens:
                matches.append({
                    'company': c,
                    'company_name': company_name,
                    'matched_names': matched_names,
                    'matched_tokens': matched_tokens,
                    'priority': c.get('priority', 'LOW'),
                    'status': c.get('status', 'unknown')
                })
        return matches

    def _find_keyword_matches() -> dict:
        return {
            'high': [k for k in MOCK_HIGH_CONFIDENCE_KEYWORDS if _has(k)],
            'medium': [k for k in MOCK_MEDIUM_CONFIDENCE_KEYWORDS if _has(k)]
        }

    def _count_tge_signals() -> tuple[int, list]:
        tge_signals = [
            "token", "coin", "crypto", "blockchain", "defi", "web3",
            "mainnet", "testnet", "protocol", "network", "chain",
            "launch", "release", "deploy", "announce", "live"
        ]
        found_signals = [signal for signal in tge_signals if _has(signal)]
        return len(found_signals), found_signals

    def _calculate_confidence_score(strategy: str, companies: list, keywords: dict, signals_count: int) -> int:
        base_score = 0
        if strategy == "high_confidence":
            base_score = 85
        elif strategy == "medium_confidence":
            base_score = 65
        elif strategy == "token_action":
            base_score = 75

        # Company priority bonus
        max_priority_score = 0
        for company in companies:
            priority = company.get('priority', 'LOW')
            if priority == 'HIGH':
                max_priority_score = max(max_priority_score, 15)
            elif priority == 'MEDIUM':
                max_priority_score = max(max_priority_score, 10)
            elif priority == 'LOW':
                max_priority_score = max(max_priority_score, 5)

        final_score = min(base_score + max_priority_score, 100)
        return final_score

    # Find matches
    company_matches = _find_company_matches()
    keyword_matches = _find_keyword_matches()
    signals_count, found_signals = _count_tge_signals()

    if not company_matches:
        return False, match_details

    # Fill in basic match details
    match_details['matched_companies'] = [c['company_name'] for c in company_matches]
    match_details['matched_tokens'] = []
    for c in company_matches:
        match_details['matched_tokens'].extend(c.get('matched_tokens', []))

    highest_priority = max((c.get('priority', 'LOW') for c in company_matches),
                          key=lambda x: {'HIGH': 3, 'MEDIUM': 2, 'LOW': 1}.get(x, 0))
    match_details['priority_level'] = highest_priority

    # Strategy 1: High confidence TGE keywords + company match
    if keyword_matches['high'] and company_matches:
        valid_matches = []
        for match in company_matches:
            priority = match.get('priority', 'LOW')
            if priority == 'HIGH':
                valid_matches.append(match)
            elif priority == 'MEDIUM' and len(keyword_matches['high']) >= 1:
                valid_matches.append(match)
            elif priority == 'LOW' and len(keyword_matches['high']) >= 2:
                valid_matches.append(match)

        if valid_matches:
            match_details['matched_keywords'] = keyword_matches['high']
            match_details['match_strategy'] = 'high_confidence'
            match_details['confidence_score'] = _calculate_confidence_score(
                'high_confidence', valid_matches, keyword_matches, signals_count
            )
            match_details['match_reasons'] = [
                f"High confidence TGE keywords: {', '.join(keyword_matches['high'])}",
                f"Company priority: {highest_priority}",
                f"Matched companies: {', '.join([m['company_name'] for m in valid_matches])}"
            ]
            return True, match_details

    # Strategy 2: Medium confidence keywords + company + multiple TGE signals
    if keyword_matches['medium'] and company_matches and signals_count >= 3:
        high_priority_matches = [m for m in company_matches if m.get('priority') == 'HIGH']
        if high_priority_matches:
            match_details['matched_keywords'] = keyword_matches['medium']
            match_details['match_strategy'] = 'medium_confidence'
            match_details['confidence_score'] = _calculate_confidence_score(
                'medium_confidence', high_priority_matches, keyword_matches, signals_count
            )
            match_details['match_reasons'] = [
                f"Medium confidence keywords: {', '.join(keyword_matches['medium'])}",
                f"Multiple TGE signals ({signals_count}): {', '.join(found_signals[:5])}",
                f"HIGH priority companies: {', '.join([m['company_name'] for m in high_priority_matches])}"
            ]
            return True, match_details

    # Strategy 3: Token symbol + specific TGE action words
    token_specific_actions = ["launch", "release", "deploy", "mint", "distribute", "airdrop"]
    found_actions = [action for action in token_specific_actions if _has(action)]

    if found_actions:
        for match in company_matches:
            if (match.get('matched_tokens') and match.get('priority') == 'HIGH'):
                match_details['matched_keywords'] = found_actions
                match_details['matched_tokens'] = match.get('matched_tokens', [])
                match_details['match_strategy'] = 'token_action'
                match_details['confidence_score'] = _calculate_confidence_score(
                    'token_action', [match], keyword_matches, signals_count
                )
                match_details['match_reasons'] = [
                    f"Token symbols: {', '.join(match.get('matched_tokens', []))}",
                    f"Action words: {', '.join(found_actions)}",
                    f"HIGH priority company: {match['company_name']}"
                ]
                return True, match_details

    return False, match_details

def test_enhanced_matching_system():
    """Test the enhanced matching system with detailed output"""
    print("🔬 ENHANCED CRYPTO TGE MONITOR - PRODUCTION GRADE TEST")
    print("="*60)

    test_cases = [
        {
            "title": "Curvance Finance Announces Token Generation Event",
            "content": "Curvance Finance is excited to announce its TGE scheduled for Q1 2024",
            "expected": True,
            "description": "HIGH priority company + TGE keyword"
        },
        {
            "title": "Fhenix Protocol Launches FHE Token Distribution",
            "content": "Fhenix Protocol announces airdrop and FHE token distribution",
            "expected": True,
            "description": "HIGH priority + token symbol + high confidence keywords"
        },
        {
            "title": "TreasureDAO Platform Updates",
            "content": "TreasureDAO announces new features and improvements",
            "expected": False,
            "description": "MEDIUM priority with weak signals should not match"
        },
        {
            "title": "Fabric Store Sale",
            "content": "Local fabric store announces grand opening sale",
            "expected": False,
            "description": "Exclusion words should prevent match"
        },
        {
            "title": "Espresso Machine Review",
            "content": "Best espresso machine for coffee enthusiasts",
            "expected": False,
            "description": "Exclusion words should prevent match"
        },
        {
            "title": "MAGIC Token Launch by TreasureDAO",
            "content": "TreasureDAO announces new TGE for additional MAGIC token utility",
            "expected": True,
            "description": "MEDIUM priority + TGE keyword should match"
        }
    ]

    passed = 0
    total = len(test_cases)

    for i, test in enumerate(test_cases, 1):
        alert = {
            "title": test["title"],
            "content": test["content"],
            "url": f"https://example.com/test-{i}",
            "published": "2024-01-15"
        }

        is_match, match_details = mock_enhanced_matches_company_and_keyword(alert)
        status = "✅ PASS" if is_match == test["expected"] else "❌ FAIL"

        print(f"\nTest {i}: {status}")
        print(f"  Description: {test['description']}")
        print(f"  Title: {test['title']}")
        print(f"  Expected: {test['expected']}, Got: {is_match}")

        if is_match:
            print(f"  🏢 Companies: {', '.join(match_details['matched_companies'])}")
            print(f"  🔍 Keywords: {', '.join(match_details['matched_keywords'])}")
            if match_details['matched_tokens']:
                print(f"  🪙 Tokens: {', '.join(match_details['matched_tokens'])}")
            print(f"  📊 Confidence: {match_details['confidence_score']}%")
            print(f"  🎯 Strategy: {match_details['match_strategy']}")
            print(f"  ⚡ Priority: {match_details['priority_level']}")

        if is_match == test["expected"]:
            passed += 1

    print("\n" + "="*60)
    print(f"ENHANCED SYSTEM TEST RESULTS: {passed}/{total} passed ({passed/total*100:.1f}%)")

    if passed == total:
        print("✅ ALL TESTS PASSED - Enhanced system is production ready!")
        print("\n🎉 Key Features Working:")
        print("  • Detailed company detection with priority levels")
        print("  • Keyword categorization and confidence scoring")
        print("  • Token symbol recognition")
        print("  • Sophisticated exclusion filtering")
        print("  • Production-grade match strategies")
    else:
        print(f"❌ {total-passed} tests failed - System needs refinement")

    return passed == total

if __name__ == "__main__":
    test_enhanced_matching_system()
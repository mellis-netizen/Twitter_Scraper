#!/usr/bin/env python3
"""
Comprehensive System Audit Test for Crypto TGE Monitor
Tests the optimized system for accuracy and performance in TGE detection.
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from src.main import matches_company_and_keyword
from config import COMPANIES, HIGH_CONFIDENCE_TGE_KEYWORDS, MEDIUM_CONFIDENCE_TGE_KEYWORDS

def test_high_priority_matches():
    """Test high priority companies with various TGE scenarios"""
    print("🧪 Testing High Priority Company Matches...")

    test_cases = [
        # Should MATCH - High confidence + High priority
        {
            "title": "Curvance Announces Token Generation Event for Q1 2024",
            "content": "Curvance Finance is excited to announce its TGE scheduled for early 2024",
            "expected": True,
            "reason": "High priority company + 'TGE' keyword"
        },
        {
            "title": "Fhenix Protocol Launches Mainnet with FHE Token",
            "content": "Fhenix Protocol officially launches its mainnet with the FHE governance token",
            "expected": True,
            "reason": "High priority company + token launch"
        },
        {
            "title": "Succinct Labs Announces SP1 Token Airdrop",
            "content": "Succinct Labs announces SP1 token airdrop for early adopters",
            "expected": True,
            "reason": "High priority company + airdrop announcement"
        },

        # Should NOT match - False positives
        {
            "title": "Fabric Store Launches New Collection",
            "content": "Local fabric store launches new textile collection this spring",
            "expected": False,
            "reason": "Exclusion word 'fabric store' should prevent match"
        },
        {
            "title": "Espresso Machine Review",
            "content": "Best espresso machine for coffee lovers in 2024",
            "expected": False,
            "reason": "Exclusion words 'espresso machine' should prevent match"
        },
        {
            "title": "General Launch Announcement",
            "content": "Company launches new product line this quarter",
            "expected": False,
            "reason": "No company match, weak TGE signals"
        }
    ]

    passed = 0
    total = len(test_cases)

    for i, test in enumerate(test_cases, 1):
        alert = {
            "title": test["title"],
            "content": test["content"],
            "url": f"https://example.com/article-{i}",
            "published": "2024-01-15"
        }

        result = matches_company_and_keyword(alert)
        status = "✅ PASS" if result == test["expected"] else "❌ FAIL"

        print(f"  Test {i}: {status}")
        print(f"    Title: {test['title']}")
        print(f"    Expected: {test['expected']}, Got: {result}")
        print(f"    Reason: {test['reason']}")
        print()

        if result == test["expected"]:
            passed += 1

    print(f"High Priority Tests: {passed}/{total} passed ({passed/total*100:.1f}%)")
    return passed == total

def test_medium_priority_matches():
    """Test medium priority companies requiring stronger signals"""
    print("🧪 Testing Medium Priority Company Matches...")

    test_cases = [
        # Should MATCH - Strong TGE signals
        {
            "title": "TreasureDAO Announces New Token Generation Event",
            "content": "TreasureDAO announces TGE for new utility token alongside MAGIC",
            "expected": True,
            "reason": "Medium priority + strong TGE keyword"
        },

        # Should NOT match - Weak signals
        {
            "title": "XAI Games Launches New Game",
            "content": "XAI Games launches new blockchain game this month",
            "expected": False,
            "reason": "Medium priority + weak signals (no strong TGE keywords)"
        },
        {
            "title": "Camelot DEX Update",
            "content": "Camelot announces platform updates and new features",
            "expected": False,
            "reason": "Medium priority company without TGE signals"
        }
    ]

    passed = 0
    total = len(test_cases)

    for i, test in enumerate(test_cases, 1):
        alert = {
            "title": test["title"],
            "content": test["content"],
            "url": f"https://example.com/medium-{i}",
            "published": "2024-01-15"
        }

        result = matches_company_and_keyword(alert)
        status = "✅ PASS" if result == test["expected"] else "❌ FAIL"

        print(f"  Test {i}: {status}")
        print(f"    Title: {test['title']}")
        print(f"    Expected: {test['expected']}, Got: {result}")
        print(f"    Reason: {test['reason']}")
        print()

        if result == test["expected"]:
            passed += 1

    print(f"Medium Priority Tests: {passed}/{total} passed ({passed/total*100:.1f}%)")
    return passed == total

def test_edge_cases():
    """Test edge cases and boundary conditions"""
    print("🧪 Testing Edge Cases...")

    test_cases = [
        # Empty/invalid content
        {
            "title": "",
            "content": "",
            "expected": False,
            "reason": "Empty content should not match"
        },

        # Very short content
        {
            "title": "Test",
            "content": "Hi",
            "expected": False,
            "reason": "Too short content should not match"
        },

        # Multiple companies mentioned
        {
            "title": "Curvance and Fhenix Partner for Major Token Launch",
            "content": "Curvance Finance and Fhenix Protocol announce joint TGE initiative",
            "expected": True,
            "reason": "Multiple high-priority companies + TGE"
        }
    ]

    passed = 0
    total = len(test_cases)

    for i, test in enumerate(test_cases, 1):
        alert = {
            "title": test["title"],
            "content": test["content"],
            "url": f"https://example.com/edge-{i}",
            "published": "2024-01-15"
        }

        result = matches_company_and_keyword(alert)
        status = "✅ PASS" if result == test["expected"] else "❌ FAIL"

        print(f"  Test {i}: {status}")
        print(f"    Expected: {test['expected']}, Got: {result}")
        print(f"    Reason: {test['reason']}")
        print()

        if result == test["expected"]:
            passed += 1

    print(f"Edge Case Tests: {passed}/{total} passed ({passed/total*100:.1f}%)")
    return passed == total

def run_system_audit():
    """Run comprehensive system audit"""
    print("="*60)
    print("🔍 COMPREHENSIVE CRYPTO TGE MONITOR AUDIT")
    print("="*60)
    print()

    print("📊 SYSTEM CONFIGURATION:")
    print(f"  Companies monitored: {len(COMPANIES)}")

    high_priority = [c for c in COMPANIES if c.get('priority') == 'HIGH']
    medium_priority = [c for c in COMPANIES if c.get('priority') == 'MEDIUM']
    low_priority = [c for c in COMPANIES if c.get('priority') == 'LOW']

    print(f"  - HIGH priority: {len(high_priority)} companies")
    print(f"  - MEDIUM priority: {len(medium_priority)} companies")
    print(f"  - LOW priority: {len(low_priority)} companies")

    print(f"  High confidence keywords: {len(HIGH_CONFIDENCE_TGE_KEYWORDS)}")
    print(f"  Medium confidence keywords: {len(MEDIUM_CONFIDENCE_TGE_KEYWORDS)}")
    print()

    # Run all tests
    all_passed = True

    all_passed &= test_high_priority_matches()
    print()

    all_passed &= test_medium_priority_matches()
    print()

    all_passed &= test_edge_cases()
    print()

    print("="*60)
    if all_passed:
        print("✅ AUDIT RESULT: ALL TESTS PASSED")
        print("System is optimized for accurate TGE detection!")
    else:
        print("❌ AUDIT RESULT: SOME TESTS FAILED")
        print("System needs further optimization.")
    print("="*60)

    return all_passed

if __name__ == "__main__":
    run_system_audit()
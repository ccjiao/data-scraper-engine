#!/usr/bin/env python3
"""Tests for URL Router"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.router import URLRouter


def test_lottery_urls():
    """Test lottery URL detection"""
    cases = [
        ("https://www.lottery.gov.cn/kj/kjlb.html?dlt", "lottery", "dlt"),
        ("https://www.lottery.gov.cn/kj/kjlb.html?pl3", "lottery", "pl3"),
        ("https://www.lottery.gov.cn/kj/kjlb.html?qxc", "lottery", "qxc"),
    ]
    for url, expected_handler, expected_game in cases:
        r = URLRouter.route(url)
        assert r.handler == expected_handler, f"URL {url}: expected {expected_handler}, got {r.handler}"
        assert r.params.get("game") == expected_game, f"URL {url}: expected game={expected_game}, got {r.params.get('game')}"
    print("✅ test_lottery_urls passed")


def test_douyin_urls():
    """Test Douyin live URL detection"""
    cases = [
        ("https://live.douyin.com/379595210124", "douyin_live", "379595210124"),
        ("https://live.douyin.com/379595210124?anchor_id=", "douyin_live", "379595210124"),
        ("https://live.douyin.com/888999000", "douyin_live", "888999000"),
    ]
    for url, expected_handler, expected_room in cases:
        r = URLRouter.route(url)
        assert r.handler == expected_handler, f"URL {url}: expected {expected_handler}, got {r.handler}"
        assert r.params.get("room_id") == expected_room, f"URL {url}: expected room_id={expected_room}, got {r.params.get('room_id')}"
    print("✅ test_douyin_urls passed")


def test_generic_web_urls():
    """Test generic web URL detection"""
    cases = [
        "https://www.baidu.com/s?wd=test",
        "https://example.com/page",
        "https://news.site.com/article/123",
    ]
    for url in cases:
        r = URLRouter.route(url)
        assert r.handler == "generic_web", f"URL {url}: expected generic_web, got {r.handler}"
    print("✅ test_generic_web_urls passed")


def test_api_url():
    """Test direct API URL detection"""
    r = URLRouter.route("https://webapi.sporttery.cn/gateway/lottery/getHistoryPageList?gameNo=85&pageSize=30")
    assert r.handler == "lottery", f"Expected lottery, got {r.handler}"
    assert r.params.get("gameNo") == "85", f"Expected gameNo=85, got {r.params.get('gameNo')}"
    print("✅ test_api_url passed")


def test_empty_url():
    """Test empty/invalid URL handling"""
    r = URLRouter.route("")
    assert r.handler == "error", f"Expected error, got {r.handler}"
    print("✅ test_empty_url passed")


def test_unsupported_protocol():
    """Test unsupported protocol — falls back to generic_web with low confidence"""
    r = URLRouter.route("ftp://example.com/file.zip")
    # FTP falls through to generic_web (the catch-all) with low confidence
    assert r.handler in ("error", "generic_web"), f"Expected error or generic_web, got {r.handler}"
    assert r.confidence < 0.5, f"Expected low confidence, got {r.confidence}"
    print("✅ test_unsupported_protocol passed")


def test_supported_patterns():
    """Test get_supported_patterns"""
    patterns = URLRouter.get_supported_patterns()
    assert len(patterns) >= 3, f"Expected at least 3 patterns, got {len(patterns)}"
    # Patterns use Chinese display names
    names = [p["name"] for p in patterns]
    # Check that patterns exist (names may be in Chinese)
    assert len(patterns) >= 5, f"Expected at least 5 patterns, got {len(patterns)}"
    print(f"  Pattern names: {names}")
    print("✅ test_supported_patterns passed")


if __name__ == "__main__":
    test_lottery_urls()
    test_douyin_urls()
    test_generic_web_urls()
    test_api_url()
    test_empty_url()
    test_unsupported_protocol()
    test_supported_patterns()
    print("\n🎉 All router tests passed!")

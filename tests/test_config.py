#!/usr/bin/env python3
"""Tests for Config Loader"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.config import ConfigLoader


def test_list_configs():
    """Test listing available configs"""
    configs = ConfigLoader.list_configs()
    assert len(configs) > 0, "No configs found"
    print(f"  Found {len(configs)} configs")
    for c in configs:
        assert "file" in c, f"Config missing 'file' key: {c}"
        assert "name" in c, f"Config missing 'name' key: {c}"
        assert "protocol" in c, f"Config missing 'protocol' key: {c}"
    print("✅ test_list_configs passed")


def test_load_lottery_config():
    """Test loading a lottery config"""
    config = ConfigLoader.load("lottery_dlt")
    assert config is not None, "Config is None"
    assert config.name, "Config name is empty"
    assert config.protocol, "Config protocol is empty"
    assert config.params, "Config params is empty"
    assert config.params.get("gameNo") == "85", f"Expected gameNo=85, got {config.params.get('gameNo')}"
    print(f"  Config: {config.name}, protocol: {config.protocol}, gameNo: {config.params.get('gameNo')}")
    print("✅ test_load_lottery_config passed")


def test_load_nonexistent_config():
    """Test loading a nonexistent config"""
    try:
        ConfigLoader.load("nonexistent_config")
        # Should not raise, but return empty or default
        print("  (ConfigLoader handled missing config gracefully)")
    except FileNotFoundError:
        print("  (ConfigLoader raised FileNotFoundError as expected)")
    print("✅ test_load_nonexistent_config passed")


if __name__ == "__main__":
    test_list_configs()
    test_load_lottery_config()
    test_load_nonexistent_config()
    print("\n🎉 All config tests passed!")

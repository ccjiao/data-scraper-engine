# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-06-15

### Added
- ✅ GitHub Actions CI pipeline (Python 3.10-3.13 matrix, lint, test, build verify)
- ✅ Unit tests for URL router (7 test cases) and config loader (3 test cases)
- ✅ Issue templates (bug report, feature request) and PR template
- ✅ CI status badge in README
- 📦 `datapilot-pro` package v1.0.0 released
  - Sentiment analysis (94% accuracy, keyword + negation + intensity + emoji)
  - User profiling (4-dimension scoring, 5 user types, water army detection)
  - REST API server (Flask, sync/async modes, AI tool integration)
  - douyinLive Go service management (install/start/stop/restart/status)
- 📖 Pro features integration — `--analyze`, `serve`, `service` commands gracefully degrade in open-source version

### Changed
- Pro feature imports use graceful fallback with installation instructions

## [1.0.0] - 2026-06-15

### Added
- 🧠 URL smart router — auto-detect data source type from URL
- 🔄 HTTP API adapter — lottery data with pagination, retry, WAF bypass
- 🔄 WebSocket adapter — streaming data collection
- 🌐 Generic web adapter — extract tables/lists/articles from any URL
- 🎰 Lottery data: 大乐透 (Super Lotto), 排列3 (Pick 3), 七星彩 (Seven Star)
- 🎬 Douyin live stream data collection (chat, gifts, interactions)
- 📊 Styled Excel output with dark headers, number highlighting, alternating rows
- 📊 JSON and CSV output formats
- 🔧 Config-driven architecture — new data sources only need a YAML file
- 🚀 `scrape` command — one URL, full pipeline
- 📋 `list` command — show supported URL patterns and configs

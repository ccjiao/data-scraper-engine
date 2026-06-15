# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

<div align="center">

# 🚀 Data Scraper Engine

**URL in, Data out** — Throw a link, get a data report.

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![CI](https://github.com/ccjiao/data-scraper-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/ccjiao/data-scraper-engine/actions/workflows/ci.yml)
[![GitHub Stars](https://img.shields.io/github/stars/ccjiao/data-scraper-engine?style=social)](https://github.com/ccjiao/data-scraper-engine)

A **URL-driven intelligent data scraping engine** that automatically identifies link types, scrapes data, and outputs structured results. Zero config, one command, full pipeline.

[English](#features) · [中文文档](#中文说明) · [Pro Features](#pro-features) · [Contributing](CONTRIBUTING.md)

</div>

---

## ✨ Features

- 🧠 **Smart URL Routing** — Drop any URL, auto-detect the data source type (lottery / live stream / generic web)
- 🔄 **Multi-Protocol** — HTTP API + WebSocket + Generic Web, one engine for all sources
- 📊 **Structured Output** — Excel (.xlsx) with styled headers, JSON, CSV out of the box
- 🎰 **Lottery Data** — Full historical data for China Sports Lottery (大乐透 / 排列3 / 七星彩)
- 🎬 **Live Stream** — Douyin (TikTok China) live room data collection (chat, gifts, interactions)
- 🌐 **Generic Web** — Any URL → extract tables, lists, articles automatically
- 🔌 **AI Integration** — REST API + MCP protocol for OpenClaw / WorkBuddy / any AI tool

## 🚀 Quick Start

### Install

```bash
git clone https://github.com/ccjiao/data-scraper-engine.git
cd data-scraper-engine
pip install -r requirements.txt
```

### One Command to Scrape

```bash
# 🎰 Lottery — just paste the URL
python scripts/scraper.py scrape "https://www.lottery.gov.cn/kj/kjlb.html?dlt"

# 🎬 Douyin Live — paste the room URL
python scripts/scraper.py scrape "https://live.douyin.com/379595210124" --duration 600

# 🌐 Any website — auto-extract structured data
python scripts/scraper.py scrape "https://example.com" --format json
```

That's it. No config files, no selectors, no code.

### How It Works

```
URL → Smart Router → Auto-detect type → Choose adapter → Scrape → Parse → Output
```

The engine recognizes these URL patterns automatically:

| URL Pattern | Type | Example |
|---|---|---|
| `lottery.gov.cn/kj/kjlb.html?dlt` | 大乐透 (Super Lotto) | [Link](https://www.lottery.gov.cn/kj/kjlb.html?dlt) |
| `lottery.gov.cn/kj/kjlb.html?pl3` | 排列3 (Pick 3) | [Link](https://www.lottery.gov.cn/kj/kjlb.html?pl3) |
| `lottery.gov.cn/kj/kjlb.html?qxc` | 七星彩 (Seven Star) | [Link](https://www.lottery.gov.cn/kj/kjlb.html?qxc) |
| `live.douyin.com/{room_id}` | Douyin Live Room | [Link](https://live.douyin.com/) |
| Any other URL | Generic Web Page | — |

## 📖 Usage

### Core Command: `scrape`

```bash
python scripts/scraper.py scrape <URL> [options]
```

| Option | Description | Default |
|---|---|---|
| `--output PATH` | Output file path | `~/Desktop/<name>.xlsx` |
| `--format FORMAT` | Output format: xlsx, json, csv | xlsx |
| `--analyze` | Run intelligent analysis (Pro) | off |
| `--start DATE` | Start date YYYY-MM-DD (lottery) | — |
| `--end DATE` | End date YYYY-MM-DD (lottery) | — |
| `--keywords KW` | Keyword filter, comma-separated (live) | — |
| `--duration SEC` | Collection duration in seconds (live) | — |
| `--direct` | Direct connection mode (live, no proxy) | off |

### Legacy Subcommands

```bash
# Lottery (advanced options)
python scripts/scraper.py lottery --game dlt --start 2025-01-01 --end 2025-12-31

# Douyin Live (advanced options)
python scripts/scraper.py douyin-live --room 379595210124 --analyze --duration 300

# List supported sources
python scripts/scraper.py list
```

### Python SDK

```python
from engine.router import URLRouter
from engine.config import ConfigLoader
from engine.adapters import get_adapter

# Route any URL
route = URLRouter.route("https://www.lottery.gov.cn/kj/kjlb.html?dlt")
print(f"Type: {route.label}, Handler: {route.handler}")

# Use the matched adapter
config = ConfigLoader.load(route.config_name)
adapter = get_adapter(config.protocol)
for batch in adapter.collect():
    process(batch)
```

## 🏗️ Architecture

```
data-scraper-engine/
├── engine/                    # Core engine
│   ├── router.py              # URL smart router (regex matching + param extraction)
│   ├── config.py              # YAML config loader
│   ├── core.py                # Scraper engine core
│   ├── adapters/              # Protocol adapters
│   │   ├── base.py            # Abstract base adapter
│   │   ├── http_api.py        # HTTP API adapter (lottery, etc.)
│   │   ├── websocket.py       # WebSocket adapter (live streams)
│   │   └── generic_web.py     # Generic web scraper (BeautifulSoup)
│   ├── parsers/               # Data parsers
│   │   └── lottery_parser.py  # Lottery number parsing
│   └── outputs/               # Output writers
│       ├── excel_writer.py    # Styled Excel output
│       ├── json_writer.py     # JSON output
│       └── csv_writer.py      # CSV output
├── configs/                   # YAML data source configs
│   ├── lottery_dlt.yaml       # 大乐透
│   ├── lottery_pl3.yaml       # 排列3
│   └── douyin_live.yaml       # Douyin live
└── scripts/                   # CLI entry points
    ├── scraper.py             # Main CLI (scrape/lottery/douyin-live/list)
    └── douyin_live_client.py  # Douyin live WebSocket client
```

### How to Add a New Data Source

1. Create a YAML config in `configs/`
2. Add URL pattern rules in `engine/router.py`
3. (Optional) Create a custom adapter in `engine/adapters/`

No other code changes needed — the engine auto-discovers configs and adapters.

## ⭐ Pro Features

The open-source engine covers all core scraping functionality. **Pro features** are available in the `datapilot-pro` package:

| Feature | Open Source | Pro |
|---|:---:|:---:|
| URL smart routing | ✅ | ✅ |
| Lottery data scraping | ✅ | ✅ |
| Douyin live scraping | ✅ | ✅ |
| Generic web scraping | ✅ | ✅ |
| Excel / JSON / CSV output | ✅ | ✅ |
| Sentiment analysis | — | ✅ 94% accuracy |
| User profiling | — | ✅ 4-dimension scoring |
| Water army detection | — | ✅ |
| REST API server | — | ✅ Flask API |
| douyinLive Go proxy | — | ✅ Auto install/manage |
| Scheduled tasks | — | ✅ |
| Webhook push | — | ✅ |

```bash
pip install datapilot-pro
```

After installing, Pro features automatically integrate into the CLI:

```bash
# Sentiment analysis + user profiling
python scripts/scraper.py scrape "https://live.douyin.com/379595210124" --analyze --duration 300

# REST API server
python scripts/scraper.py serve --port 9898

# douyinLive Go service management
python scripts/scraper.py service start
```

Or use in Python:

```python
from datapilot_pro.analyzers import SentimentAnalyzer, UserProfileAnalyzer

analyzer = SentimentAnalyzer()
result = analyzer.analyze("这个产品质量好！")
# → {"sentiment": "positive", "score": 0.75, ...}
```

## 🛡️ Compliance & Safety

This tool is designed for **legitimate data collection only**:

- ✅ Only scrapes publicly accessible data
- ✅ Respects `robots.txt` protocols
- ✅ Built-in rate limiting (HTTP interval ≥ 0.3s)
- ✅ No personal private information collection (phone, ID, etc.)
- ✅ Users must comply with local laws (Cybersecurity Law, PIPL, etc.)

**You are responsible for ensuring your use complies with applicable laws and regulations.**

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

**Ways to contribute:**
- 🐛 Report bugs via [Issues](https://github.com/ccjiao/data-scraper-engine/issues)
- 💡 Suggest new data source adapters
- 🔧 Submit Pull Requests
- ⭐ Star this repo if you find it useful!

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

## 中文说明

**丢一个链接，还你一份数据报告。**

data-scraper-engine 是一款 URL 驱动的智能数据采集引擎，只需提交一个链接，系统自动完成链接识别 → 数据采集 → 结构化输出的全链路处理。

### 核心优势

1. **零配置** — 丢链接即用，不需要写选择器、配规则
2. **智能路由** — 自动识别彩票/直播/网页等链接类型
3. **多协议** — HTTP API + WebSocket + 通用网页，一套引擎搞定
4. **可集成** — REST API + MCP 协议，AI 工具直接调用
5. **开箱即用** — Excel 精美排版输出，告别乱码

### 快速开始

```bash
# 克隆项目
git clone https://github.com/ccjiao/data-scraper-engine.git
cd data-scraper-engine
pip install -r requirements.txt

# 一键抓取大乐透
python scripts/scraper.py scrape "https://www.lottery.gov.cn/kj/kjlb.html?dlt"

# 抓取抖音直播间
python scripts/scraper.py scrape "https://live.douyin.com/379595210124" --duration 600

# 抓取任意网页
python scripts/scraper.py scrape "https://example.com"
```

### 安全边界

- ✅ 仅采集公开可访问数据
- ✅ 遵守 robots.txt 协议
- ✅ 内置频率限制（HTTP 请求间隔 ≥ 0.3s）
- ❌ 不采集个人隐私信息
- ⚠️ 使用者需自行遵守《网络安全法》《个人信息保护法》等法律法规

---

<div align="center">
Made with ❤️ by <a href="https://github.com/ccjiao">ccjiao</a> · 苏界网络 · 丝鹿传媒
</div>

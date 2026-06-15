#!/usr/bin/env python3
"""
data-scraper-engine 通用数据采集引擎 v4.0 — URL驱动，一键抓取

用法:
  # ★ 核心用法：给个链接就行
  python scraper.py scrape https://www.lottery.gov.cn/kj/kjlb.html?dlt
  python scraper.py scrape https://live.douyin.com/379595210124 --duration 600
  python scraper.py scrape https://example.com --format json

  # 高级用法（指定参数）
  python scraper.py scrape <URL> --analyze --output ~/Desktop/结果.xlsx
  python scraper.py scrape <URL> --keywords 价格,链接 --duration 300

  # 传统子命令（兼容旧版）
  python scraper.py lottery --game dlt
  python scraper.py douyin-live --room 379595210124 --analyze

  # API服务模式（供AI工具集成）
  python scraper.py serve --port 9898

  # 服务管理
  python scraper.py service start
"""

import argparse
import json
import sys
import os

# 将项目根目录加入Python路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from engine.config import ConfigLoader
from engine.router import URLRouter


# 彩票游戏编号映射
LOTTERY_GAME_MAP = {
    "dlt": {"config": "lottery_dlt", "gameNo": "85", "name": "大乐透"},
    "pl3": {"config": "lottery_pl3", "gameNo": "35", "name": "排列3"},
    "qxc": {"config": "lottery_qxc", "gameNo": "04", "name": "七星彩"},
}


# ============================================================
# 核心：URL驱动的一键抓取
# ============================================================

def cmd_scrape(args):
    """
    URL驱动的一键抓取 — 给一个链接，自动识别+采集+输出
    这是v4.0的核心入口
    """
    url = args.url

    # 1. 智能路由 — 识别链接类型
    route = URLRouter.route(url)

    print(f"\n{'='*60}")
    print(f"  data-scraper-engine v4.0")
    print(f"  链接类型: {route.label} ({route.handler})")
    print(f"  置信度: {route.confidence:.0%}")
    print(f"  URL: {url}")
    print(f"{'='*60}\n")

    if route.handler == "error":
        print(f"  [✗] {route.params.get('error', '无法识别的链接')}")
        return []

    # 2. 根据路由分发到对应处理器
    if route.handler == "lottery":
        return _handle_lottery(route, args)
    elif route.handler == "douyin_live":
        return _handle_douyin_live(route, args)
    elif route.handler == "generic_web":
        return _handle_generic_web(route, args)
    else:
        print(f"  [✗] 未知处理器: {route.handler}")
        return []


def _handle_lottery(route, args):
    """处理彩票数据采集"""
    params = route.params
    game = params.get("game", "dlt")
    gameNo = params.get("gameNo", "85")
    config_name = params.get("config", "lottery_dlt")

    # 如果gameNo有值但game未知，反查
    if game == "unknown" and gameNo:
        game = URLRouter._gameNo_to_game(gameNo)
        config_name = LOTTERY_GAME_MAP.get(game, {}).get("config", "lottery_dlt")

    if game not in LOTTERY_GAME_MAP:
        print(f"  [✗] 无法识别彩种 (gameNo={gameNo})")
        return []

    game_info = LOTTERY_GAME_MAP[game]
    config = ConfigLoader.load(config_name)
    config.params["gameNo"] = game_info["gameNo"]

    # 日期过滤
    if args.start:
        config.params["beginDate"] = args.start
    if args.end:
        config.params["endDate"] = args.end

    output = args.output or os.path.expanduser(f"~/Desktop/{game_info['name']}历史开奖数据.xlsx")
    output_format = args.format or "xlsx"

    from engine.adapters import get_adapter
    adapter_cls = get_adapter(config.protocol)
    adapter = adapter_cls(config)

    from engine.parsers.lottery_parser import LotteryParser
    parser = LotteryParser(config)

    all_records = []
    for batch in adapter.collect(start_date=args.start, end_date=args.end):
        parsed_batch = [parser.parse(record) for record in batch]
        all_records.extend(parsed_batch)

    if all_records:
        from engine.outputs import get_writer
        writer = get_writer(output_format, config.output.get("style", {}))
        writer.write(all_records, output,
                     columns=config.output.get("columns"),
                     title=config.name,
                     style_config=config.output.get("style", {}))

    print(f"\n  总计: {len(all_records)} 条记录 → {output}")
    return all_records


def _handle_douyin_live(route, args):
    """处理抖音直播数据采集"""
    room_id = route.params.get("room_id")
    if not room_id:
        # 尝试从URL中提取
        import re
        match = re.search(r"(\d+)", args.url)
        if match:
            room_id = match.group(1)
        else:
            print("  [✗] 无法从URL中提取直播间ID")
            return []

    keywords = []
    if args.keywords:
        keywords = [kw.strip() for kw in args.keywords.split(",") if kw.strip()]

    use_proxy = not args.direct
    proxy_port = args.proxy_port or 1088

    from scripts.douyin_live_client import DouyinLiveCollector
    collector = DouyinLiveCollector(room_id, keywords,
                                    use_proxy=use_proxy, proxy_port=proxy_port)

    output = args.output or os.path.expanduser(f"~/Desktop/抖音直播_{room_id}.xlsx")
    output_format = args.format or "xlsx"

    messages = collector.collect(duration=args.duration)

    if not messages:
        print("\n  未采集到消息数据")
        return []

    if args.analyze:
        messages = _run_analysis(messages, room_id, output, output_format)
    else:
        if messages:
            from engine.outputs import get_writer
            writer = get_writer(output_format)
            writer.write(messages, output, title="抖音直播数据")

    return messages


def _handle_generic_web(route, args):
    """处理通用网页抓取"""
    from engine.config import DataSourceConfig

    config = DataSourceConfig({
        "name": route.label,
        "protocol": "generic_web",
        "endpoint": args.url,
        "request": {
            "timeout": 30,
        },
    })

    from engine.adapters.generic_web import GenericWebAdapter
    adapter = GenericWebAdapter(config)

    all_records = []
    for batch in adapter.collect():
        all_records.extend(batch)

    if all_records:
        output = args.output or os.path.expanduser("~/Desktop/网页数据.xlsx")
        output_format = args.format or "xlsx"

        # 为通用网页数据生成列定义
        columns = _infer_columns(all_records)

        from engine.outputs import get_writer
        writer = get_writer(output_format)
        writer.write(all_records, output,
                     columns=columns,
                     title=config.name)

    print(f"\n  总计: {len(all_records)} 条记录")
    return all_records


def _infer_columns(records: list[dict]) -> list[dict]:
    """从数据中推断列定义"""
    if not records:
        return []

    # 收集所有key
    all_keys = []
    seen = set()
    for r in records:
        for k in r:
            if k not in seen and not k.startswith("_"):
                all_keys.append(k)
                seen.add(k)

    columns = []
    for key in all_keys:
        col = {"key": key, "label": key, "width": 20}
        # 根据内容调整宽度
        max_len = 0
        for r in records[:50]:
            val = str(r.get(key, ""))
            # 估算中文字符宽度
            char_len = sum(2 if ord(c) > 127 else 1 for c in val)
            max_len = max(max_len, char_len)
        if max_len > 0:
            col["width"] = min(max(max_len + 2, 10), 50)
        columns.append(col)

    return columns


# ============================================================
# 智能分析
# ============================================================

def _run_analysis(messages, room_id, output_path, output_format):
    """执行智能分析（Pro 功能 — 开源版需安装 datapilot-pro）"""
    try:
        from engine.analyzers.sentiment import SentimentAnalyzer
        from engine.analyzers.user_profile import UserProfileAnalyzer
    except ImportError:
        print(f"\n  ⚠️  智能分析是 Pro 功能")
        print(f"  开源版不包含情感分析和用户画像模块。")
        print(f"  获取 Pro 版:")
        print(f"    pip install datapilot-pro")
        print(f"    或访问 https://github.com/ccjiao/data-scraper-engine#pro-features")
        print()
        # 开源版仍然输出采集数据
        if messages:
            from engine.outputs import get_writer
            writer = get_writer(output_format)
            writer.write(messages, output_path, title="抖音直播数据")
        return messages

    print(f"\n{'='*50}")
    print(f"  智能分析报告")
    print(f"{'='*50}")

    # ---- 1. 弹幕情感分析 ----
    print(f"\n  弹幕情感分析")
    print(f"  {'-'*40}")

    sentiment_analyzer = SentimentAnalyzer()
    chat_messages = [m for m in messages if m.get("type") == "chat"]

    if chat_messages:
        enriched = sentiment_analyzer.analyze_batch(chat_messages)
        stats = sentiment_analyzer.get_stats()

        print(f"  总弹幕数: {stats.get('total', 0)}")
        print(f"  正面: {stats.get('positive', 0)} ({stats.get('positive_ratio', 0):.1%})")
        print(f"  负面: {stats.get('negative', 0)} ({stats.get('negative_ratio', 0):.1%})")
        print(f"  中性: {stats.get('neutral', 0)} ({stats.get('neutral_ratio', 0):.1%})")
        print(f"  情感指数: {stats.get('sentiment_index', 0):+.2f} (-1=极度负面, +1=极度正面)")

        trend = sentiment_analyzer.get_trend(window_seconds=60)
        if trend:
            print(f"\n  情感趋势 (1分钟窗口):")
            for t in trend[-5:]:
                bar = "+" * int((t["avg_score"] + 1) * 10)
                print(f"    {t['window_start']}: {t['avg_score']:+.2f} {bar} ({t['count']}条)")

        positive_chats = [m for m in enriched if m.get("sentiment") == "positive"]
        negative_chats = [m for m in enriched if m.get("sentiment") == "negative"]

        if positive_chats:
            print(f"\n  正面代表弹幕:")
            for m in positive_chats[:3]:
                print(f"    [{m.get('nickname', '?')}]: {m.get('content', '')[:50]}")

        if negative_chats:
            print(f"\n  负面代表弹幕:")
            for m in negative_chats[:3]:
                print(f"    [{m.get('nickname', '?')}]: {m.get('content', '')[:50]}")

        for i, msg in enumerate(messages):
            if msg.get("type") == "chat":
                for em in enriched:
                    if em.get("timestamp") == msg.get("timestamp") and em.get("content") == msg.get("content"):
                        msg["sentiment"] = em.get("sentiment", "neutral")
                        msg["sentiment_score"] = em.get("sentiment_score", 0)
                        break

    # ---- 2. 用户画像分析 ----
    print(f"\n\n  用户画像分析")
    print(f"  {'-'*40}")

    profile_analyzer = UserProfileAnalyzer()
    profile_analyzer.process_batch(messages)
    groups = profile_analyzer.classify_all()
    user_stats = profile_analyzer.get_stats()

    print(f"  总用户数: {user_stats.get('total_users', 0)}")
    print(f"  消费用户: {user_stats.get('gift_users', 0)} ({user_stats.get('gift_user_ratio', 0):.1%})")
    print(f"  总打赏额: {user_stats.get('total_gift_value', 0)} 抖币")

    type_labels = {
        "whale": "鲸鱼用户", "dolphin": "海豚用户",
        "minnow": "小鱼用户", "lurker": "潜水用户",
        "suspect": "疑似水军",
    }

    type_dist = user_stats.get("type_distribution", {})
    for type_name, count in sorted(type_dist.items(), key=lambda x: -x[1]):
        label = type_labels.get(type_name, type_name)
        print(f"    {label}: {count}")

    top_users = profile_analyzer.get_top_users(5, by="gift_value")
    if top_users:
        print(f"\n  打赏Top5:")
        for u in top_users:
            tags = "/".join(u.get("tags", [])[:3])
            print(f"    {u['nickname']}: {u['gift_value']}抖币 ({tags})")

    suspects = profile_analyzer.detect_suspects()
    if suspects:
        print(f"\n  疑似水军 ({len(suspects)}人):")
        for s in suspects[:3]:
            flags = ", ".join(s.get("flags", []))
            print(f"    {s['nickname']}: 疑似度{s['suspect_score']:.0%} ({flags})")

    # ---- 3. 生成分析报告文件 ----
    report_dir = os.path.dirname(output_path) or os.path.expanduser("~/Desktop")
    report_name = os.path.splitext(os.path.basename(output_path))[0]

    if chat_messages:
        sentiment_report = sentiment_analyzer.generate_report()
        sentiment_path = os.path.join(report_dir, f"{report_name}_情感分析.json")
        with open(sentiment_path, "w", encoding="utf-8") as f:
            json.dump(sentiment_report, f, ensure_ascii=False, indent=2)
        print(f"\n  [OK] 情感分析报告: {sentiment_path}")

    profile_report = profile_analyzer.generate_report()
    profile_path = os.path.join(report_dir, f"{report_name}_用户画像.json")
    with open(profile_path, "w", encoding="utf-8") as f:
        json.dump(profile_report, f, ensure_ascii=False, indent=2)
    print(f"  [OK] 用户画像报告: {profile_path}")

    if messages:
        from engine.outputs import get_writer
        writer = get_writer(output_format)
        writer.write(messages, output_path, title="抖音直播数据")

    return messages


# ============================================================
# 传统子命令（兼容旧版）
# ============================================================

def cmd_lottery(args):
    """彩票数据采集"""
    game = args.game
    if game not in LOTTERY_GAME_MAP:
        print(f"不支持的彩种: {game}")
        print(f"支持: {', '.join(LOTTERY_GAME_MAP.keys())}")
        return

    game_info = LOTTERY_GAME_MAP[game]
    config = ConfigLoader.load(game_info["config"])
    config.params["gameNo"] = game_info["gameNo"]

    if args.start:
        config.params["beginDate"] = args.start
    if args.end:
        config.params["endDate"] = args.end

    output = args.output or os.path.expanduser(f"~/Desktop/{game_info['name']}历史开奖数据.xlsx")
    output_format = args.format or "xlsx"

    from engine.adapters import get_adapter
    adapter_cls = get_adapter(config.protocol)
    adapter = adapter_cls(config)

    from engine.parsers.lottery_parser import LotteryParser
    parser = LotteryParser(config)

    all_records = []
    for batch in adapter.collect(start_date=args.start, end_date=args.end):
        parsed_batch = [parser.parse(record) for record in batch]
        all_records.extend(parsed_batch)

    if all_records:
        from engine.outputs import get_writer
        writer = get_writer(output_format, config.output.get("style", {}))
        writer.write(all_records, output,
                     columns=config.output.get("columns"),
                     title=config.name,
                     style_config=config.output.get("style", {}))

    print(f"\n  总计: {len(all_records)} 条记录")
    return all_records


def cmd_douyin_live(args):
    """抖音直播数据采集"""
    room_input = args.room or args.url
    if not room_input:
        print("请通过 --room 或 --url 指定直播间")
        return

    keywords = []
    if args.keywords:
        keywords = [kw.strip() for kw in args.keywords.split(",") if kw.strip()]

    use_proxy = not args.direct
    proxy_port = args.proxy_port or 1088

    from scripts.douyin_live_client import DouyinLiveCollector
    collector = DouyinLiveCollector(room_input, keywords,
                                    use_proxy=use_proxy, proxy_port=proxy_port)

    output = args.output or os.path.expanduser(f"~/Desktop/抖音直播_{collector.room_id}.xlsx")
    output_format = args.format or "xlsx"

    messages = collector.collect(duration=args.duration)

    if not messages:
        print("\n  未采集到消息数据")
        return []

    if args.analyze:
        messages = _run_analysis(messages, collector.room_id, output, output_format)
    else:
        if messages:
            from engine.outputs import get_writer
            writer = get_writer(output_format)
            writer.write(messages, output, title="抖音直播数据")

    return messages


def cmd_service(args):
    """douyinLive 服务管理（Pro 功能 — 开源版需安装 datapilot-pro）"""
    try:
        from scripts.douyinlive_service import DouyinLiveService
    except ImportError:
        print("\n  ⚠️  douyinLive 服务管理是 Pro 功能")
        print("  开源版不包含 Go 服务管理模块。")
        print("  获取 Pro 版: pip install datapilot-pro")
        print()
        return

    svc = DouyinLiveService(port=args.port or 1088)

    if args.service_cmd == "install":
        svc.install(go_bin=args.go)
    elif args.service_cmd == "start":
        svc.start(config_path=args.config)
    elif args.service_cmd == "stop":
        svc.stop()
    elif args.service_cmd == "restart":
        svc.restart()
    elif args.service_cmd == "status":
        svc.print_status()
    else:
        print("用法: scraper.py service [install|start|stop|restart|status]")


def cmd_list(args):
    """列出可用配置和URL模式"""
    configs = ConfigLoader.list_configs()
    patterns = URLRouter.get_supported_patterns()

    print(f"\n{'='*60}")
    print(f"  可用数据源")
    print(f"{'='*60}")

    if patterns:
        print(f"\n  支持的URL模式:")
        for p in patterns:
            print(f"    {p['name']:<10} ({p['type']})")

    if configs:
        print(f"\n  配置文件:")
        for c in configs:
            print(f"    {c['file']:<25} [{c['protocol']:<10}] {c['name']}")

    print(f"\n  提示: 使用 scrape <URL> 自动识别链接类型")
    print()


def cmd_serve(args):
    """启动API服务（Pro 功能 — 开源版需安装 datapilot-pro）"""
    try:
        from scripts.api_server import start_server
        start_server(host=args.host, port=args.port)
    except ImportError:
        print("\n  ⚠️  API 服务是 Pro 功能")
        print("  开源版不包含 REST API 服务模块。")
        print("  获取 Pro 版:")
        print("    pip install datapilot-pro")
        print("  或使用 CLI 模式:")
        print("    python scraper.py scrape <URL>")
        print()


# ============================================================
# 主入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="data-scraper-engine 通用数据采集引擎 v4.0 — URL驱动，一键抓取",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
核心用法 — 给个链接就行:
  %(prog)s scrape https://www.lottery.gov.cn/kj/kjlb.html?dlt
  %(prog)s scrape https://live.douyin.com/379595210124 --duration 600
  %(prog)s scrape https://example.com

高级用法:
  %(prog)s scrape <URL> --analyze --output ~/Desktop/结果.xlsx
  %(prog)s scrape <URL> --keywords 价格,链接 --duration 300
  %(prog)s scrape <URL> --direct  (抖音直连模式)

传统子命令:
  %(prog)s lottery --game dlt
  %(prog)s douyin-live --room 379595210124 --analyze

API服务 (供AI工具集成):
  %(prog)s serve --port 9898
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="命令")

    # ---- scrape: 核心子命令 ----
    scrape_parser = subparsers.add_parser("scrape",
        help="URL驱动一键抓取 (核心用法)")
    scrape_parser.add_argument("url", help="目标URL — 自动识别类型并抓取")
    scrape_parser.add_argument("--output", help="输出文件路径")
    scrape_parser.add_argument("--format", choices=["xlsx", "json", "csv"],
                               help="输出格式 (默认xlsx)")
    scrape_parser.add_argument("--analyze", action="store_true",
                               help="开启智能分析 (情感+用户画像)")
    scrape_parser.add_argument("--start", help="开始日期 (YYYY-MM-DD, 彩票)")
    scrape_parser.add_argument("--end", help="结束日期 (YYYY-MM-DD, 彩票)")
    scrape_parser.add_argument("--keywords", help="关键词过滤 (逗号分隔, 直播)")
    scrape_parser.add_argument("--duration", type=int, default=None,
                               help="采集时长/秒 (直播)")
    scrape_parser.add_argument("--direct", action="store_true",
                               help="直连模式 (不使用代理, 直播)")
    scrape_parser.add_argument("--proxy-port", type=int, default=1088,
                               help="代理端口 (默认1088)")

    # ---- lottery: 彩票子命令 ----
    lottery_parser = subparsers.add_parser("lottery", help="彩票数据采集")
    lottery_parser.add_argument("--game", required=True, choices=["dlt", "pl3", "qxc"],
                                help="彩种: dlt=大乐透, pl3=排3, qxc=七星彩")
    lottery_parser.add_argument("--start", help="开始日期 (YYYY-MM-DD)")
    lottery_parser.add_argument("--end", help="结束日期 (YYYY-MM-DD)")
    lottery_parser.add_argument("--output", help="输出文件路径")
    lottery_parser.add_argument("--format", choices=["xlsx", "json", "csv"], help="输出格式")

    # ---- douyin-live: 直播子命令 ----
    douyin_parser = subparsers.add_parser("douyin-live", help="抖音直播数据采集")
    douyin_parser.add_argument("--room", help="直播间ID (如 379595210124)")
    douyin_parser.add_argument("--url", help="直播间URL (自动提取ID)")
    douyin_parser.add_argument("--duration", type=int, default=None,
                               help="采集时长(秒)")
    douyin_parser.add_argument("--keywords", help="弹幕关键词过滤，逗号分隔")
    douyin_parser.add_argument("--analyze", action="store_true",
                               help="开启智能分析")
    douyin_parser.add_argument("--direct", action="store_true",
                               help="直连模式")
    douyin_parser.add_argument("--proxy-port", type=int, default=1088,
                               help="代理端口 (默认1088)")
    douyin_parser.add_argument("--output", help="输出文件路径")
    douyin_parser.add_argument("--format", choices=["xlsx", "json", "csv"], help="输出格式")

    # ---- serve: API服务 ----
    serve_parser = subparsers.add_parser("serve", help="启动API服务 (供AI工具集成)")
    serve_parser.add_argument("--host", default="0.0.0.0", help="监听地址")
    serve_parser.add_argument("--port", type=int, default=9898, help="监听端口")

    # ---- service: 服务管理 ----
    service_parser = subparsers.add_parser("service", help="douyinLive服务管理")
    service_parser.add_argument("service_cmd",
                               choices=["install", "start", "stop", "restart", "status"],
                               help="服务操作")
    service_parser.add_argument("--port", type=int, default=1088, help="服务端口")
    service_parser.add_argument("--config", help="配置文件路径")
    service_parser.add_argument("--go", help="Go可执行文件路径 (仅install)")

    # ---- list: 列出配置 ----
    subparsers.add_parser("list", help="列出可用配置和URL模式")

    args = parser.parse_args()

    if args.command == "scrape":
        cmd_scrape(args)
    elif args.command == "lottery":
        cmd_lottery(args)
    elif args.command == "douyin-live":
        cmd_douyin_live(args)
    elif args.command == "serve":
        cmd_serve(args)
    elif args.command == "service":
        cmd_service(args)
    elif args.command == "list":
        cmd_list(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

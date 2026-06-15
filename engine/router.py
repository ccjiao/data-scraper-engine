"""
URL 智能路由器 - 根据链接自动识别数据源类型并匹配处理器

支持的 URL 模式:
  - lottery.gov.cn/kj/*        → 彩票数据
  - webapi.sporttery.cn/*      → 彩票API数据
  - live.douyin.com/*          → 抖音直播间
  - 其他 URL                    → 通用网页抓取
"""

import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse, parse_qs


@dataclass
class RouteResult:
    """路由匹配结果"""
    handler: str                    # 处理器类型: lottery / douyin_live / generic_web
    source_type: str                # 数据源分类标识
    label: str                      # 中文标签
    params: dict = field(default_factory=dict)   # 提取的参数
    config_name: Optional[str] = None            # 对应的YAML配置名
    confidence: float = 1.0        # 匹配置信度 0~1


class URLRouter:
    """URL智能路由器 - 输入URL，输出处理方案"""

    # 路由规则定义 (按优先级排序)
    RULES = [
        # ---- 彩票 ----
        {
            "name": "lottery_dlt",
            "handler": "lottery",
            "source_type": "lottery_dlt",
            "label": "大乐透",
            "patterns": [
                r"lottery\.gov\.cn/kj/kjlb\.html\?dlt",
                r"lottery\.gov\.cn/kj/kjlb\.html\?.*dlt",
            ],
            "params": {"game": "dlt", "gameNo": "85", "config": "lottery_dlt"},
        },
        {
            "name": "lottery_pl3",
            "handler": "lottery",
            "source_type": "lottery_pl3",
            "label": "排列3",
            "patterns": [
                r"lottery\.gov\.cn/kj/kjlb\.html\?pl3",
                r"lottery\.gov\.cn/kj/kjlb\.html\?.*pl3",
            ],
            "params": {"game": "pl3", "gameNo": "35", "config": "lottery_pl3"},
        },
        {
            "name": "lottery_qxc",
            "handler": "lottery",
            "source_type": "lottery_qxc",
            "label": "七星彩",
            "patterns": [
                r"lottery\.gov\.cn/kj/kjlb\.html\?qxc",
                r"lottery\.gov\.cn/kj/kjlb\.html\?.*qxc",
            ],
            "params": {"game": "qxc", "gameNo": "04", "config": "lottery_qxc"},
        },
        {
            "name": "lottery_api",
            "handler": "lottery",
            "source_type": "lottery_api",
            "label": "体彩API数据",
            "patterns": [
                r"webapi\.sporttery\.cn",
                r"c\.apiclient\.sporttery\.cn",
            ],
            "params": {},  # 需要从URL参数中提取 gameNo
            "extract_params": True,
        },
        # ---- 抖音直播 ----
        {
            "name": "douyin_live",
            "handler": "douyin_live",
            "source_type": "douyin_live",
            "label": "抖音直播间",
            "patterns": [
                r"live\.douyin\.com/(\d+)",
                r"live\.douyin\.com/\?room_id=(\d+)",
                r"www\.iesdouyin\.com/live\?room_id=(\d+)",
            ],
            "extract_room_id": True,
        },
        # ---- 通用网页 ----
        {
            "name": "generic_web",
            "handler": "generic_web",
            "source_type": "generic_web",
            "label": "网页内容",
            "patterns": [r"https?://"],  # 兜底：所有HTTP(S)链接
            "params": {},
            "confidence": 0.5,  # 低置信度，表示兜底方案
        },
    ]

    @classmethod
    def route(cls, url: str) -> RouteResult:
        """
        根据URL自动路由到对应处理器

        Args:
            url: 任意URL字符串

        Returns:
            RouteResult: 路由结果，包含处理器类型和提取的参数
        """
        url = url.strip()
        if not url:
            return RouteResult(
                handler="error",
                source_type="empty",
                label="空链接",
                params={"error": "请提供有效的URL"},
            )

        for rule in cls.RULES:
            for pattern in rule["patterns"]:
                match = re.search(pattern, url)
                if match:
                    params = dict(rule.get("params", {}))
                    confidence = rule.get("confidence", 1.0)

                    # 提取直播间ID
                    if rule.get("extract_room_id") and match.groups():
                        params["room_id"] = match.group(1)

                    # 从URL查询参数中提取
                    if rule.get("extract_params"):
                        parsed = urlparse(url)
                        qs = parse_qs(parsed.query)
                        if "gameNo" in qs:
                            params["gameNo"] = qs["gameNo"][0]
                            params["game"] = cls._gameNo_to_game(params["gameNo"])

                    return RouteResult(
                        handler=rule["handler"],
                        source_type=rule["source_type"],
                        label=rule["label"],
                        params=params,
                        config_name=params.get("config"),
                        confidence=confidence,
                    )

        # 理论上不会到这里（generic_web 兜底），但以防万一
        return RouteResult(
            handler="generic_web",
            source_type="unknown",
            label="未知来源",
            params={"url": url},
            confidence=0.3,
        )

    @classmethod
    def _gameNo_to_game(cls, gameNo: str) -> str:
        """gameNo 反向映射到游戏标识"""
        mapping = {"85": "dlt", "35": "pl3", "04": "qxc", "350": "pl5"}
        return mapping.get(gameNo, "unknown")

    @classmethod
    def get_supported_patterns(cls) -> list[dict]:
        """返回所有支持的URL模式（用于帮助文档）"""
        result = []
        for rule in cls.RULES:
            if rule["name"] == "generic_web":
                continue  # 不显示兜底规则
            result.append({
                "name": rule["label"],
                "type": rule["handler"],
                "examples": rule["patterns"],
            })
        return result

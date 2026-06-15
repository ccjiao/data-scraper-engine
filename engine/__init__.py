"""
data-scraper-engine 通用数据采集引擎
URL驱动 · 配置驱动 · 协议适配器 · 多输出格式
"""

from engine.core import ScraperEngine
from engine.config import ConfigLoader

__version__ = "1.0.0"
__all__ = ["ScraperEngine", "ConfigLoader"]

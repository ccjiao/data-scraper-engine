"""
配置加载器 - YAML驱动的数据源定义
"""

import os
import yaml
from pathlib import Path
from typing import Any


CONFIGS_DIR = Path(__file__).parent.parent / "configs"


class DataSourceConfig:
    """单个数据源的配置对象"""

    def __init__(self, config_dict: dict):
        self._raw = config_dict
        self.name = config_dict.get("name", "unnamed")
        self.protocol = config_dict.get("protocol", "http_api")
        self.description = config_dict.get("description", "")

        # 连接配置
        self.endpoint = config_dict.get("endpoint", "")
        self.headers = config_dict.get("headers", {})
        self.params = config_dict.get("params", {})
        self.cookies = config_dict.get("cookies", {})

        # 分页配置
        self.pagination = config_dict.get("pagination", {})

        # WebSocket配置
        self.websocket = config_dict.get("websocket", {})

        # 签名配置
        self.sign = config_dict.get("sign", {})

        # 编码配置
        self.encoding = config_dict.get("encoding", "json")

        # 消息类型映射
        self.message_types = config_dict.get("message_types", [])

        # 数据路径映射
        self.data_path = config_dict.get("data_path", "data")

        # 过滤配置
        self.filters = config_dict.get("filters", {})

        # 输出配置
        self.output = config_dict.get("output", {})

        # 请求配置
        self.request = config_dict.get("request", {})
        self.interval = self.request.get("interval", 0.3)
        self.timeout = self.request.get("timeout", 30)
        self.retries = self.request.get("retries", 3)
        self.retry_delay = self.request.get("retry_delay", 2)

        # 日期过滤
        self.date_range = config_dict.get("date_range", {})

    def get(self, key: str, default: Any = None) -> Any:
        return self._raw.get(key, default)

    def __repr__(self):
        return f"<DataSourceConfig name={self.name} protocol={self.protocol}>"


class ConfigLoader:
    """YAML配置文件加载器"""

    @staticmethod
    def load(config_path: str) -> DataSourceConfig:
        """从YAML文件加载配置"""
        path = Path(config_path)
        if not path.is_absolute():
            path = CONFIGS_DIR / path
        if not path.exists():
            # 尝试加.yaml后缀
            yaml_path = Path(str(path) + ".yaml")
            if yaml_path.exists():
                path = yaml_path
            else:
                raise FileNotFoundError(f"配置文件不存在: {config_path}")

        with open(path, "r", encoding="utf-8") as f:
            config_dict = yaml.safe_load(f) or {}

        return DataSourceConfig(config_dict)

    @staticmethod
    def load_from_dict(config_dict: dict) -> DataSourceConfig:
        """从字典创建配置"""
        return DataSourceConfig(config_dict)

    @staticmethod
    def list_configs() -> list:
        """列出所有可用配置"""
        configs = []
        if CONFIGS_DIR.exists():
            for f in CONFIGS_DIR.glob("*.yaml"):
                try:
                    with open(f, "r", encoding="utf-8") as fh:
                        d = yaml.safe_load(fh) or {}
                    configs.append({
                        "file": f.name,
                        "name": d.get("name", f.stem),
                        "protocol": d.get("protocol", "unknown"),
                        "description": d.get("description", ""),
                    })
                except Exception:
                    configs.append({
                        "file": f.name,
                        "name": f.stem,
                        "protocol": "error",
                        "description": "配置解析失败",
                    })
        return configs

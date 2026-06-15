"""
协议适配器基类 - 定义统一接口
"""

from abc import ABC, abstractmethod
from typing import Any, Generator


class BaseAdapter(ABC):
    """数据采集适配器基类，所有协议适配器必须继承此类"""

    def __init__(self, config):
        self.config = config
        self.name = config.name
        self._collected_count = 0

    @abstractmethod
    def collect(self, **kwargs) -> Generator[list[dict], None, None]:
        """
        执行数据采集，以生成器方式返回批量数据

        Yields:
            list[dict]: 每次yield一批数据记录
        """
        pass

    @abstractmethod
    def validate_config(self) -> tuple[bool, str]:
        """
        验证配置是否有效

        Returns:
            (bool, str): (是否有效, 错误信息)
        """
        pass

    def get_stats(self) -> dict:
        """返回采集统计信息"""
        return {
            "name": self.name,
            "protocol": self.config.protocol,
            "collected_count": self._collected_count,
        }

    def _increment(self, count: int = 1):
        self._collected_count += count

"""
数据采集引擎核心调度器
配置驱动 · 协议适配 · 多格式输出
"""

import sys
import time
from pathlib import Path

from engine.config import ConfigLoader, DataSourceConfig
from engine.adapters import get_adapter
from engine.outputs import get_writer


class ScraperEngine:
    """通用数据采集引擎"""

    def __init__(self, config: DataSourceConfig):
        self.config = config
        self.adapter = None
        self.writer = None
        self._all_records = []

    def run(self, output_path: str = None, output_format: str = None,
            **kwargs) -> list[dict]:
        """
        执行采集任务

        Args:
            output_path: 输出文件路径
            output_format: 输出格式 (xlsx/json/csv)，默认从配置读取
            **kwargs: 传递给适配器的参数

        Returns:
            list[dict]: 采集到的全部数据
        """
        print(f"\n{'='*60}")
        print(f"  数据采集引擎 v2.0")
        print(f"  数据源: {self.config.name}")
        print(f"  协议: {self.config.protocol}")
        print(f"{'='*60}\n")

        # 创建适配器
        adapter_cls = get_adapter(self.config.protocol)
        self.adapter = adapter_cls(self.config)

        # 创建输出器
        fmt = output_format or self.config.output.get("format", "xlsx")
        output_cfg = self.config.output.get("style", {})
        self.writer = get_writer(fmt, output_cfg)

        # 执行采集
        start_time = time.time()
        self._all_records = []

        try:
            for batch in self.adapter.collect(**kwargs):
                self._all_records.extend(batch)
        except KeyboardInterrupt:
            print("\n  [!] 用户中断采集")
        except Exception as e:
            print(f"\n  [!] 采集出错: {e}")
            import traceback
            traceback.print_exc()

        elapsed = time.time() - start_time

        # 输出统计
        stats = self.adapter.get_stats()
        print(f"\n{'='*60}")
        print(f"  采集完成！")
        print(f"  总记录数: {len(self._all_records)}")
        print(f"  耗时: {elapsed:.1f}s")
        if stats.get("detail"):
            for k, v in stats["detail"].items():
                print(f"  {k}: {v}")
        print(f"{'='*60}\n")

        # 写入文件
        if output_path and self._all_records:
            columns = self.config.output.get("columns")
            title = self.config.name
            style_config = self.config.output.get("style", {})
            self.writer.write(self._all_records, output_path,
                              columns=columns, title=title,
                              style_config=style_config)

        return self._all_records

    def get_records(self) -> list[dict]:
        """获取已采集的数据"""
        return self._all_records

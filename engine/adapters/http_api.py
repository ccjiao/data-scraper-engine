"""
HTTP API 适配器 - 通用REST API数据采集
支持：分页、日期过滤、WAF绕过、指数退避重试
"""

import time
import json
import requests
from typing import Generator

from engine.adapters.base import BaseAdapter


class HttpApiAdapter(BaseAdapter):
    """HTTP API数据采集适配器"""

    def __init__(self, config):
        super().__init__(config)
        self.session = requests.Session()
        self.session.headers.update(config.headers)
        if config.cookies:
            self.session.cookies.update(config.cookies)
        self._total_pages = None
        self._total_records = None

    def validate_config(self) -> tuple[bool, str]:
        if not self.config.endpoint:
            return False, "endpoint 不能为空"
        if self.config.pagination.get("type") not in ("page_number", "cursor", "none", None, ""):
            return False, f"不支持的分页类型: {self.config.pagination.get('type')}"
        return True, ""

    def collect(self, **kwargs) -> Generator[list[dict], None, None]:
        """按页采集数据"""
        valid, msg = self.validate_config()
        if not valid:
            raise ValueError(f"配置验证失败: {msg}")

        pagination_type = self.config.pagination.get("type", "page_number")

        if pagination_type == "page_number":
            yield from self._collect_by_page(**kwargs)
        elif pagination_type == "cursor":
            yield from self._collect_by_cursor(**kwargs)
        else:
            yield from self._collect_single(**kwargs)

    def _collect_by_page(self, start_page=1, end_page=None,
                         start_date=None, end_date=None, **kwargs) -> Generator[list[dict], None, None]:
        """按页码分页采集"""
        page = start_page
        consecutive_empty = 0

        while True:
            params = dict(self.config.params)
            params["pageNo"] = page

            # 日期参数注入
            if start_date:
                params["beginDate"] = start_date
            if end_date:
                params["endDate"] = end_date

            try:
                data = self._fetch_page(params)
            except Exception as e:
                print(f"  [!] 第{page}页请求失败: {e}")
                retry_count = 0
                while retry_count < self.config.retries:
                    retry_count += 1
                    delay = self.config.retry_delay * (2 ** (retry_count - 1))
                    print(f"  [↻] 第{retry_count}次重试，等待{delay}s...")
                    time.sleep(delay)
                    try:
                        data = self._fetch_page(params)
                        break
                    except Exception as e2:
                        if retry_count == self.config.retries:
                            print(f"  [✗] 重试{self.config.retries}次后仍失败，跳过")
                            return
                        continue

            # 解析数据
            records = self._extract_records(data)
            if not records:
                consecutive_empty += 1
                if consecutive_empty >= 3:
                    print(f"  [✓] 连续3页无数据，采集完成")
                    break
                page += 1
                continue

            consecutive_empty = 0

            # 更新统计
            self._extract_metadata(data)
            self._increment(len(records))

            yield records

            # 日志
            total_info = f"/{self._total_pages}" if self._total_pages else ""
            print(f"  [✓] 第{page}页: {len(records)}条{total_info} | 累计: {self._collected_count}条")

            # 检查是否最后一页
            if self._total_pages and page >= self._total_pages:
                print(f"  [✓] 已到达最后一页({self._total_pages})，采集完成")
                break

            if end_page and page >= end_page:
                print(f"  [✓] 已到达指定结束页({end_page})，采集完成")
                break

            page += 1
            time.sleep(self.config.interval)

    def _collect_by_cursor(self, **kwargs) -> Generator[list[dict], None, None]:
        """按游标分页采集"""
        cursor = None
        while True:
            params = dict(self.config.params)
            if cursor:
                params["cursor"] = cursor

            data = self._fetch_page(params)
            records = self._extract_records(data)
            if not records:
                break

            self._increment(len(records))
            yield records

            next_cursor = self._extract_cursor(data)
            if not next_cursor or next_cursor == cursor:
                break
            cursor = next_cursor
            time.sleep(self.config.interval)

    def _collect_single(self, **kwargs) -> Generator[list[dict], None, None]:
        """单次请求采集（无分页）"""
        data = self._fetch_page(self.config.params)
        records = self._extract_records(data)
        if records:
            self._increment(len(records))
            yield records

    def _fetch_page(self, params: dict) -> dict:
        """请求单页数据"""
        resp = self.session.get(
            self.config.endpoint,
            params=params,
            timeout=self.config.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def _extract_records(self, data: dict) -> list[dict]:
        """从响应中提取数据列表"""
        data_path = self.config.pagination.get("data_path") or self.config.data_path
        if not data_path:
            return data if isinstance(data, list) else []

        # 支持点号分隔的路径，如 value.list
        parts = data_path.split(".")
        current = data
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part, [])
            else:
                return []

        return current if isinstance(current, list) else []

    def _extract_metadata(self, data: dict):
        """提取分页元数据"""
        if self._total_pages is None:
            pages_path = self.config.pagination.get("total_pages_path")
            if pages_path:
                self._total_pages = self._get_nested(data, pages_path)

        if self._total_records is None:
            total_path = self.config.pagination.get("total_records_path")
            if total_path:
                self._total_records = self._get_nested(data, total_path)

    def _extract_cursor(self, data: dict) -> str:
        """提取下一页游标"""
        cursor_path = self.config.pagination.get("cursor_path", "cursor")
        return self._get_nested(data, cursor_path)

    @staticmethod
    def _get_nested(data: dict, path: str):
        """按点号分隔路径获取嵌套值"""
        parts = path.split(".")
        current = data
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current

    def get_stats(self) -> dict:
        stats = super().get_stats()
        stats["total_pages"] = self._total_pages
        stats["total_records"] = self._total_records
        return stats

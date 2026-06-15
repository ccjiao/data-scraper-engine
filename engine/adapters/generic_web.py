"""
通用网页适配器 - 兜底抓取方案

对于不匹配任何已知模式的URL，使用 requests+BeautifulSoup 抓取网页内容，
提取标题、正文、表格、列表等结构化数据。

能力:
  - 智能编码检测（charset_normalizer / HTTP头 / meta标签）
  - 提取: 标题 / 正文段落 / 表格 / 列表 / 链接 / 图片
  - 表格自动转结构化数据（适合Excel输出）
  - 优雅降级: JS渲染页面也能提取meta/noscript内容
"""

import time
import re
from typing import Generator
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from engine.adapters.base import BaseAdapter


class GenericWebAdapter(BaseAdapter):
    """通用网页数据采集适配器"""

    def __init__(self, config):
        super().__init__(config)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        })
        self._url = config.endpoint or config.params.get("url", "")

    def validate_config(self) -> tuple[bool, str]:
        if not self._url:
            return False, "URL 不能为空"
        if not self._url.startswith(("http://", "https://")):
            return False, "URL 必须以 http:// 或 https:// 开头"
        return True, ""

    def collect(self, **kwargs) -> Generator[list[dict], None, None]:
        """采集网页内容"""
        valid, msg = self.validate_config()
        if not valid:
            raise ValueError(f"配置验证失败: {msg}")

        url = kwargs.get("url", self._url)
        timeout = self.config.timeout or 30

        # 1. 请求网页
        print(f"  [→] 正在请求: {url}")
        try:
            resp = self.session.get(url, timeout=timeout, allow_redirects=True)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"  [✗] 请求失败: {e}")
            return

        # 2. 智能编码检测
        content = self._decode_response(resp)

        # 3. 解析HTML
        soup = BeautifulSoup(content, "html.parser")

        # 4. 提取结构化数据
        records = []

        # --- 标题 ---
        title = self._extract_title(soup)

        # --- 元信息 ---
        meta_info = self._extract_meta(soup)

        # --- 表格数据（最结构化，优先） ---
        table_records = self._extract_tables(soup, url)
        if table_records:
            records.extend(table_records)

        # --- 列表数据 ---
        list_records = self._extract_lists(soup, url)
        if list_records:
            records.extend(list_records)

        # --- 正文段落 ---
        paragraph_records = self._extract_paragraphs(soup, url)
        if paragraph_records:
            records.extend(paragraph_records)

        # --- 如果完全没提取到内容，保存元信息 ---
        if not records:
            records.append({
                "type": "page_info",
                "title": title,
                "url": url,
                "meta": meta_info,
                "content_length": len(content),
                "note": "未能提取到结构化内容，可能为JS渲染页面",
            })

        self._increment(len(records))

        # 添加页面级信息
        for r in records:
            r["_source_url"] = url
            r["_page_title"] = title
            if r.get("type") == "page_info":
                continue
            r.setdefault("meta", meta_info)

        yield records

        print(f"  [✓] 提取完成: {len(records)} 条记录")

    def _decode_response(self, resp: requests.Response) -> str:
        """智能解码响应内容"""
        # 1. 尝试 charset_normalizer
        try:
            import charset_normalizer
            result = charset_normalizer.detect(resp.content)
            if result and result.get("encoding"):
                encoding = result["encoding"]
                try:
                    return resp.content.decode(encoding)
                except (UnicodeDecodeError, LookupError):
                    pass
        except ImportError:
            pass

        # 2. HTTP Content-Type 头中的 charset
        encoding = resp.encoding
        if encoding:
            try:
                return resp.content.decode(encoding)
            except (UnicodeDecodeError, LookupError):
                pass

        # 3. HTML meta charset
        try:
            soup = BeautifulSoup(resp.content, "html.parser")
            meta_charset = soup.find("meta", charset=True)
            if meta_charset:
                enc = meta_charset.get("charset")
                return resp.content.decode(enc)
        except Exception:
            pass

        # 4. UTF-8 fallback
        try:
            return resp.content.decode("utf-8")
        except UnicodeDecodeError:
            return resp.content.decode("gbk", errors="replace")

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """提取页面标题"""
        # og:title > title > h1
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            return og_title["content"].strip()

        title_tag = soup.find("title")
        if title_tag:
            return title_tag.get_text(strip=True)

        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)

        return ""

    def _extract_meta(self, soup: BeautifulSoup) -> dict:
        """提取元信息"""
        meta = {}
        for tag in soup.find_all("meta"):
            name = tag.get("name") or tag.get("property", "")
            content = tag.get("content", "")
            if name and content:
                meta[name] = content
        return meta

    def _extract_tables(self, soup: BeautifulSoup, base_url: str) -> list[dict]:
        """提取表格数据"""
        records = []
        tables = soup.find_all("table")

        for table_idx, table in enumerate(tables):
            # 获取表头
            headers = []
            thead = table.find("thead")
            if thead:
                for th in thead.find_all(["th", "td"]):
                    headers.append(th.get_text(strip=True))

            # 如果没有 thead，尝试第一行作为表头
            rows = table.find_all("tr")
            if not headers and rows:
                first_row = rows[0]
                for cell in first_row.find_all(["th", "td"]):
                    headers.append(cell.get_text(strip=True))
                rows = rows[1:]  # 跳过表头行

            if not headers:
                # 没有表头，用列序号
                if rows:
                    first_cells = rows[0].find_all("td")
                    headers = [f"列{i+1}" for i in range(len(first_cells))]

            # 提取数据行
            for row in rows:
                cells = row.find_all(["td", "th"])
                if not cells:
                    continue

                record = {
                    "type": "table_row",
                    "table_index": table_idx + 1,
                }

                for i, cell in enumerate(cells):
                    col_name = headers[i] if i < len(headers) else f"列{i+1}"
                    text = cell.get_text(strip=True)

                    # 检查是否有链接
                    link = cell.find("a", href=True)
                    if link:
                        record[f"{col_name}_链接"] = urljoin(base_url, link["href"])

                    record[col_name] = text

                if any(v for k, v in record.items() if k not in ("type", "table_index")):
                    records.append(record)

        return records

    def _extract_lists(self, soup: BeautifulSoup, base_url: str) -> list[dict]:
        """提取列表数据（ul/ol）"""
        records = []

        # 排除导航类列表
        skip_classes = {"nav", "menu", "breadcrumb", "footer", "sidebar",
                        "header", "pagination", "social"}

        for list_tag in soup.find_all(["ul", "ol"]):
            # 跳过导航
            parent_class = " ".join(list_tag.parent.get("class", [])) if list_tag.parent else ""
            if any(sc in parent_class.lower() for sc in skip_classes):
                continue
            tag_class = " ".join(list_tag.get("class", []))
            if any(sc in tag_class.lower() for sc in skip_classes):
                continue

            items = list_tag.find_all("li", recursive=False)
            if len(items) < 2:  # 少于2项的列表不提取
                continue

            for item in items:
                text = item.get_text(strip=True)
                if not text or len(text) < 2:
                    continue

                record = {
                    "type": "list_item",
                    "content": text[:500],  # 限制长度
                }

                link = item.find("a", href=True)
                if link:
                    record["link"] = urljoin(base_url, link["href"])

                records.append(record)

        return records[:100]  # 限制列表项数量

    def _extract_paragraphs(self, soup: BeautifulSoup, base_url: str) -> list[dict]:
        """提取正文段落"""
        records = []

        # 移除不需要的标签
        for tag in soup.find_all(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        # 查找正文区域
        content_area = (
            soup.find("article")
            or soup.find("main")
            or soup.find(class_=re.compile(r"content|article|post|entry", re.I))
            or soup.find("body")
            or soup
        )

        if not content_area:
            return []

        for p in content_area.find_all("p"):
            text = p.get_text(strip=True)
            # 过滤过短或无意义内容
            if len(text) < 10:
                continue
            # 过滤导航/版权类文字
            if re.match(r"(版权|©|备案号|ICP|all rights reserved)", text, re.I):
                continue

            record = {
                "type": "paragraph",
                "content": text[:1000],
            }

            links = []
            for a in p.find_all("a", href=True):
                links.append({
                    "text": a.get_text(strip=True),
                    "url": urljoin(base_url, a["href"]),
                })
            if links:
                record["links"] = links

            records.append(record)

        return records[:200]  # 限制段落数量

    def get_stats(self) -> dict:
        stats = super().get_stats()
        stats["url"] = self._url
        return stats

"""CSV输出器"""

import csv
import os


class CsvWriter:
    def __init__(self, config: dict = None):
        self.config = config or {}

    def write(self, records: list[dict], output_path: str, **kwargs):
        if not records:
            print("  [!] 无数据可写入")
            return
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        keys = list(records[0].keys())
        with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(records)
        print(f"  [✓] 已保存: {output_path} ({len(records)}条)")

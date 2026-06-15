"""JSON输出器"""

import json
import os


class JsonWriter:
    def __init__(self, config: dict = None):
        self.config = config or {}

    def write(self, records: list[dict], output_path: str, **kwargs):
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2, default=str)
        print(f"  [✓] 已保存: {output_path} ({len(records)}条)")

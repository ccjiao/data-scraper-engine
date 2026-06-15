"""
输出模块 - Excel/CSV/JSON 多格式输出
"""

from engine.outputs.excel_writer import ExcelWriter
from engine.outputs.json_writer import JsonWriter
from engine.outputs.csv_writer import CsvWriter

OUTPUT_REGISTRY = {
    "xlsx": ExcelWriter,
    "excel": ExcelWriter,
    "json": JsonWriter,
    "csv": CsvWriter,
}


def get_writer(format_name: str, config: dict = None):
    """根据格式名获取输出器"""
    writer_cls = OUTPUT_REGISTRY.get(format_name.lower())
    if not writer_cls:
        raise ValueError(
            f"不支持的输出格式: {format_name}\n"
            f"支持: {', '.join(OUTPUT_REGISTRY.keys())}"
        )
    return writer_cls(config)

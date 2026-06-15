from engine.adapters.base import BaseAdapter
from engine.adapters.http_api import HttpApiAdapter
from engine.adapters.websocket import WebSocketAdapter
from engine.adapters.generic_web import GenericWebAdapter

ADAPTER_REGISTRY = {
    "http_api": HttpApiAdapter,
    "websocket": WebSocketAdapter,
    "generic_web": GenericWebAdapter,
}


def get_adapter(protocol: str):
    """根据协议类型获取适配器类"""
    adapter = ADAPTER_REGISTRY.get(protocol)
    if not adapter:
        raise ValueError(
            f"不支持的协议类型: {protocol}\n"
            f"支持的协议: {', '.join(ADAPTER_REGISTRY.keys())}"
        )
    return adapter

"""
WebSocket 适配器 - 实时流数据采集
支持：抖音直播、快手直播等WebSocket实时数据流
依赖：douyinLive等第三方服务做协议转换
"""

import json
import time
import threading
from typing import Generator

from engine.adapters.base import BaseAdapter


class WebSocketAdapter(BaseAdapter):
    """WebSocket实时数据采集适配器"""

    def __init__(self, config):
        super().__init__(config)
        self._ws = None
        self._running = False
        self._message_buffer = []
        self._buffer_lock = threading.Lock()
        self._stats = {
            "chat_count": 0,
            "gift_count": 0,
            "like_count": 0,
            "member_count": 0,
            "social_count": 0,
            "system_count": 0,
            "unknown_count": 0,
        }

    def validate_config(self) -> tuple[bool, str]:
        ws_config = self.config.websocket
        if not ws_config.get("server"):
            return False, "websocket.server 不能为空（如 ws://127.0.0.1:1088）"
        if not ws_config.get("room_id"):
            return False, "websocket.room_id 不能为空（直播间ID）"
        return True, ""

    def collect(self, duration=None, keywords=None, **kwargs) -> Generator[list[dict], None, None]:
        """
        实时采集WebSocket消息

        Args:
            duration: 采集时长（秒），None表示持续到直播结束
            keywords: 关键词过滤列表，None表示不过滤
        """
        valid, msg = self.validate_config()
        if not valid:
            raise ValueError(f"配置验证失败: {msg}")

        ws_config = self.config.websocket
        server = ws_config["server"]
        room_id = ws_config["room_id"]

        # 构造WebSocket URL
        ws_url = f"{server}/ws/{room_id}"

        # 安装检查
        try:
            import websocket
        except ImportError:
            print("  [!] 安装 websocket-client...")
            import subprocess
            import sys
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", "websocket-client",
                "--quiet",
            ])
            import websocket

        print(f"  [→] 连接直播间: {ws_url}")

        # 设置回调
        ws = websocket.WebSocketApp(
            ws_url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )

        # 关键词过滤配置
        self._keywords = keywords or self.config.filters.get("keywords", [])
        self._running = True
        self._ws = ws

        # 启动WebSocket线程
        ws_thread = threading.Thread(target=ws.run_forever, daemon=True)
        ws_thread.start()

        # 等待连接建立
        time.sleep(2)

        # 按间隔从缓冲区取数据
        flush_interval = ws_config.get("flush_interval", 5)
        start_time = time.time()

        try:
            while self._running:
                # 检查时长限制
                if duration and (time.time() - start_time) > duration:
                    print(f"  [✓] 达到采集时长({duration}s)，停止采集")
                    break

                # 检查连接状态
                if not ws.sock or not ws.sock.connected:
                    print("  [!] WebSocket连接已断开")
                    break

                # 从缓冲区取数据
                batch = []
                with self._buffer_lock:
                    if self._message_buffer:
                        batch = self._message_buffer.copy()
                        self._message_buffer.clear()

                if batch:
                    self._increment(len(batch))
                    yield batch

                time.sleep(flush_interval)

        except KeyboardInterrupt:
            print("\n  [✓] 用户中断采集")
        finally:
            self._running = False
            ws.close()

    def _on_open(self, ws):
        print("  [✓] WebSocket连接已建立")
        # 启动心跳
        self._start_heartbeat(ws)

    def _on_message(self, ws, message):
        """处理收到的消息"""
        try:
            data = json.loads(message)
        except (json.JSONDecodeError, TypeError):
            return

        # 系统消息
        if data.get("type") == "system":
            event = data.get("event", "")
            if event == "live_status":
                is_live = data.get("live", False)
                if not is_live:
                    msg_text = data.get("message", "直播间未开播")
                    print(f"  [i] {msg_text}")
                    if "未开播" in msg_text or "已结束" in msg_text:
                        self._running = False
            self._stats["system_count"] += 1
            return

        method = data.get("method", "")

        # 方法映射
        method_map = {
            "WebcastChatMessage": "chat",
            "WebcastMemberMessage": "member",
            "WebcastGiftMessage": "gift",
            "WebcastLikeMessage": "like",
            "WebcastSocialMessage": "social",
        }

        msg_type = method_map.get(method, "unknown")
        if msg_type in self._stats:
            self._stats[msg_type + "_count"] += 1
        else:
            self._stats["unknown_count"] += 1

        # 解析为统一格式
        parsed = self._parse_message(msg_type, data)

        # 关键词过滤
        if self._keywords and msg_type == "chat":
            content = parsed.get("content", "")
            if not any(kw in content for kw in self._keywords):
                return  # 不匹配关键词，跳过

        if parsed:
            with self._buffer_lock:
                self._message_buffer.append(parsed)

    def _on_error(self, ws, error):
        print(f"  [!] WebSocket错误: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        print(f"  [i] WebSocket连接关闭: {close_status_code} {close_msg}")
        self._running = False

    def _start_heartbeat(self, ws):
        """启动心跳线程"""
        def heartbeat():
            while self._running:
                try:
                    if ws.sock and ws.sock.connected:
                        ws.send("ping")
                except Exception:
                    pass
                time.sleep(30)

        t = threading.Thread(target=heartbeat, daemon=True)
        t.start()

    def _parse_message(self, msg_type: str, data: dict) -> dict:
        """解析消息为统一格式"""
        base = {
            "type": msg_type,
            "timestamp": data.get("timestamp", time.strftime("%Y-%m-%d %H:%M:%S")),
            "room_id": data.get("room_id", ""),
            "livename": data.get("livename", ""),
        }

        if msg_type == "chat":
            raw = data.get("data", data)
            base.update({
                "nickname": raw.get("nickname", raw.get("user", {}).get("nickname", "")),
                "content": raw.get("content", raw.get("msg", "")),
                "user_id": raw.get("user_id", raw.get("user", {}).get("id", "")),
                "user_level": raw.get("user_level", ""),
            })
        elif msg_type == "gift":
            raw = data.get("data", data)
            base.update({
                "nickname": raw.get("nickname", raw.get("user", {}).get("nickname", "")),
                "gift_name": raw.get("gift_name", raw.get("giftName", "")),
                "gift_count": raw.get("gift_count", raw.get("giftCount", 1)),
                "gift_value": raw.get("gift_value", raw.get("giftValue", 0)),
                "user_id": raw.get("user_id", raw.get("user", {}).get("id", "")),
            })
        elif msg_type == "member":
            raw = data.get("data", data)
            base.update({
                "nickname": raw.get("nickname", raw.get("user", {}).get("nickname", "")),
                "current_count": raw.get("current_count", raw.get("currentCount", 0)),
                "user_id": raw.get("user_id", raw.get("user", {}).get("id", "")),
            })
        elif msg_type == "like":
            raw = data.get("data", data)
            base.update({
                "nickname": raw.get("nickname", raw.get("user", {}).get("nickname", "")),
                "like_count": raw.get("like_count", raw.get("count", 1)),
            })
        elif msg_type == "social":
            raw = data.get("data", data)
            base.update({
                "nickname": raw.get("nickname", raw.get("user", {}).get("nickname", "")),
                "action": raw.get("action", "follow"),
            })
        else:
            base["raw"] = data

        return base

    def get_stats(self) -> dict:
        stats = super().get_stats()
        stats["detail"] = dict(self._stats)
        return stats

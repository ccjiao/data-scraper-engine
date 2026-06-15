#!/usr/bin/env python3
"""
抖音直播间数据采集器 - 纯Python实现
基于 WebSocket + Protobuf 直连抖音直播消息流

依赖:
  pip install websocket-client protobuf requests py_mini_racer

技术栈:
  1. HTTP获取直播间页面 → 提取room_id + ttwid
  2. 构造WSS连接 → X-Bogus签名
  3. WebSocket长连接 → 接收二进制帧
  4. PushFrame反序列化 → Gzip解压 → Response解析
  5. 按method字段分发消息 → 提取弹幕/礼物/点赞等

参考项目:
  - https://github.com/jwwsjlm/douyinLive (Go版)
  - https://github.com/zhonghangAlex/DySpider (Python版)

⚠️ 法律合规提醒:
  - 仅采集公开直播间数据
  - 不得用于商业牟利或侵犯用户隐私
  - 遵守《网络安全法》《个人信息保护法》
  - 不得干扰平台正常运营
"""

import gzip
import json
import time
import struct
import hashlib
import threading
import re
import os
import sys
from pathlib import Path
from typing import Optional

import requests
import websocket


# Protobuf消息结构（简化版，不需要.proto文件）
# 使用手工编解码来解析抖音消息
try:
    from google.protobuf import descriptor_pb2
    from google.protobuf import json_format
    HAS_PROTOBUF = True
except ImportError:
    HAS_PROTOBUF = False


class DouyinLiveCollector:
    """抖音直播间数据采集器"""

    # 抖音WebSocket推送地址
    WSS_URL_TEMPLATE = "wss://webcast5-ws-web-lf.douyin.com/webcast/im/push/v2/"

    # 消息类型映射
    MESSAGE_TYPES = {
        "WebcastChatMessage": "chat",
        "WebcastMemberMessage": "member",
        "WebcastGiftMessage": "gift",
        "WebcastLikeMessage": "like",
        "WebcastSocialMessage": "social",
        "WebcastRoomUserSeqMessage": "room_user_seq",
        "WebcastChatMessageGBK": "chat",
        "WebcastControlMessage": "control",
        "WebcastEmojiChatMessage": "emoji_chat",
        "WebcastRoomStatsMessage": "room_stats",
    }

    def __init__(self, room_url_or_id: str, keywords: list = None,
                 use_proxy: bool = True, proxy_port: int = 1088):
        """
        Args:
            room_url_or_id: 直播间URL或ID
            keywords: 弹幕关键词过滤列表
            use_proxy: 是否使用douyinLive代理（推荐True，获取完整解码数据）
            proxy_port: douyinLive代理服务端口
        """
        self.room_id = self._extract_room_id(room_url_or_id)
        self.keywords = keywords or []
        self.use_proxy = use_proxy
        self.proxy_port = proxy_port
        self.cookies = {}
        self._running = False
        self._ws = None
        self._message_buffer = []
        self._buffer_lock = threading.Lock()
        self._stats = {
            "chat": 0, "gift": 0, "like": 0,
            "member": 0, "social": 0, "system": 0, "other": 0,
        }
        self._viewer_count = 0
        self._room_title = ""
        self._anchor_name = ""

    @staticmethod
    def _extract_room_id(input_str: str) -> str:
        """从URL或纯数字中提取直播间ID"""
        if input_str.isdigit():
            return input_str
        m = re.search(r'live\.douyin\.com/(\d+)', input_str)
        if m:
            return m.group(1)
        m = re.search(r'anchor_id=(\d+)', input_str)
        if m:
            return m.group(1)
        # 可能是短ID，尝试直接用
        return input_str.strip("/").split("/")[-1]

    def _get_live_room_info(self) -> dict:
        """获取直播间信息，提取ttwid等Cookie"""
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Referer": f"https://live.douyin.com/{self.room_id}",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        try:
            resp = requests.get(
                f"https://live.douyin.com/{self.room_id}",
                headers=headers,
                timeout=15,
                allow_redirects=True,
            )
            # 提取ttwid
            for cookie_name, cookie_value in resp.cookies.items():
                if cookie_name == "ttwid":
                    self.cookies["ttwid"] = cookie_value

            # 从HTML中提取room_id（可能是真实ID）
            text = resp.text
            m = re.search(r'"roomId"\s*:\s*"(\d+)"', text)
            if m:
                real_id = m.group(1)
                if real_id != self.room_id:
                    print(f"  [i] 真实房间ID: {real_id} (原始: {self.room_id})")
                    self.room_id = real_id

            # 提取主播名
            m = re.search(r'"nickname"\s*:\s*"([^"]+)"', text)
            if m:
                self._anchor_name = m.group(1)

            # 提取直播标题
            m = re.search(r'"title"\s*:\s*"([^"]+)"', text)
            if m:
                self._room_title = m.group(1)

            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def collect(self, duration: int = None, callback=None) -> list[dict]:
        """
        开始采集直播数据

        Args:
            duration: 采集时长（秒），None为持续到直播结束
            callback: 每收到一条消息时的回调函数

        Returns:
            采集到的全部消息列表
        """
        mode_str = "代理模式(douyinLive)" if self.use_proxy else "直连模式(简化)"
        print(f"\n  抖音直播数据采集器 v2.0 [{mode_str}]")
        print(f"  直播间: {self.room_id}")
        if self._anchor_name:
            print(f"  主播: {self._anchor_name}")
        if self._room_title:
            print(f"  标题: {self._room_title}")
        if self.keywords:
            print(f"  关键词过滤: {self.keywords}")
        if duration:
            print(f"  采集时长: {duration}s")
        print()

        if self.use_proxy:
            # === 代理模式：连接 douyinLive Go 服务 ===
            return self._collect_via_proxy(duration, callback)
        else:
            # === 直连模式：直接连接抖音 WebSocket ===
            return self._collect_direct(duration, callback)

    def _collect_via_proxy(self, duration: int = None, callback=None) -> list[dict]:
        """通过 douyinLive 代理采集（推荐，获取完整解码数据）"""
        # 检查代理服务
        import socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(("127.0.0.1", self.proxy_port))
            sock.close()
            if result != 0:
                print(f"  [!] douyinLive 代理服务未运行 (端口 {self.proxy_port})")
                print(f"  [i] 请先启动代理服务:")
                print(f"      方法1: 运行 scripts/douyinlive_service.py start")
                print(f"      方法2: docker run -p 1088:1088 ghcr.io/jwwsjlm/douyinlive:latest")
                print(f"  [i] 回退到直连模式...")
                self.use_proxy = False
                return self._collect_direct(duration, callback)
        except Exception:
            pass

        # 连接代理 WebSocket
        ws_url = f"ws://127.0.0.1:{self.proxy_port}/ws/{self.room_id}"
        print(f"  [→] 连接 douyinLive 代理: {ws_url}")

        self._running = True
        all_messages = []
        start_time = time.time()
        last_stats_time = start_time

        try:
            self._ws = websocket.WebSocketApp(
                ws_url,
                on_open=lambda ws: self._proxy_on_open(ws),
                on_message=lambda ws, msg: self._proxy_on_message(ws, msg, all_messages, callback),
                on_error=lambda ws, err: print(f"  [!] WebSocket错误: {err}"),
                on_close=lambda ws, code, msg: setattr(self, '_running', False),
            )

            ws_thread = threading.Thread(
                target=self._ws.run_forever,
                kwargs={"ping_interval": 30, "ping_timeout": 10},
                daemon=True,
            )
            ws_thread.start()
            time.sleep(1)

            while self._running:
                if duration and (time.time() - start_time) > duration:
                    print(f"\n  [✓] 达到采集时长({duration}s)，停止")
                    break

                now = time.time()
                if now - last_stats_time > 30:
                    self._print_stats()
                    last_stats_time = now

                time.sleep(1)

        except KeyboardInterrupt:
            print("\n  [!] 用户中断采集")
        finally:
            self._running = False
            if self._ws:
                self._ws.close()

        print(f"\n  采集完成！")
        print(f"  总消息数: {len(all_messages)}")
        self._print_stats()

        return all_messages

    def _proxy_on_open(self, ws):
        """代理模式 WebSocket 打开"""
        print("  [✓] 代理WebSocket连接已建立")

        # 心跳线程
        def heartbeat():
            while self._running:
                try:
                    if ws.sock:
                        ws.send("ping")
                except Exception:
                    pass
                time.sleep(10)

        t = threading.Thread(target=heartbeat, daemon=True)
        t.start()

    def _proxy_on_message(self, ws, message, all_messages, callback):
        """代理模式消息处理（JSON格式，已由Go端解码Protobuf）"""
        try:
            data = json.loads(message)
        except (json.JSONDecodeError, TypeError):
            if message == "pong":
                return
            return

        # 系统消息
        if data.get("type") == "system":
            event = data.get("event", "")
            if event == "live_status":
                live = data.get("live", True)
                msg_text = data.get("message", "")
                if not live:
                    if data.get("ended"):
                        print(f"  [i] {msg_text or '直播间已下播'}")
                        self._running = False
                    else:
                        print(f"  [i] {msg_text or '直播间未开播，等待中...'}")
                else:
                    print(f"  [✓] 直播间已开播")
                    if data.get("title"):
                        self._room_title = data["title"]
                    if data.get("livename"):
                        self._anchor_name = data["livename"]
            self._stats["system"] += 1
            return

        # 业务消息
        method = data.get("method", "")
        msg_type = self.MESSAGE_TYPES.get(method, "other")

        msg = {
            "type": msg_type,
            "method": method,
            "timestamp": data.get("timestamp", time.strftime("%Y-%m-%d %H:%M:%S")),
            "room_id": self.room_id,
        }

        # 提取主播信息
        if data.get("livename"):
            self._anchor_name = data["livename"]
        if data.get("title"):
            self._room_title = data["title"]

        user_data = data.get("user", {})

        if msg_type == "chat":
            msg["nickname"] = user_data.get("nickname", "")
            msg["content"] = data.get("content", "")
            msg["user_level"] = user_data.get("level", 0)
            msg["gender"] = user_data.get("gender", 0)
            # 关键词过滤
            if self.keywords:
                if not any(kw in msg.get("content", "") for kw in self.keywords):
                    return
            self._stats["chat"] += 1
        elif msg_type == "gift":
            msg["nickname"] = user_data.get("nickname", "")
            gift_data = data.get("gift", {})
            msg["gift_name"] = gift_data.get("name", "")
            msg["gift_count"] = data.get("count", gift_data.get("count", 1))
            msg["gift_value"] = data.get("gift_value", gift_data.get("value", 0))
            msg["gift_icon"] = gift_data.get("icon", {})
            self._stats["gift"] += 1
        elif msg_type == "member":
            msg["nickname"] = user_data.get("nickname", "")
            msg["user_level"] = user_data.get("level", 0)
            count_data = data.get("data", {})
            current_count = count_data.get("currentCount", 0) if isinstance(count_data, dict) else 0
            if current_count:
                self._viewer_count = current_count
                msg["current_count"] = current_count
            self._stats["member"] += 1
        elif msg_type == "like":
            msg["nickname"] = user_data.get("nickname", "")
            msg["like_count"] = data.get("count", 1)
            self._stats["like"] += 1
        elif msg_type == "social":
            msg["nickname"] = user_data.get("nickname", "")
            msg["action"] = "follow"
            share_data = data.get("data", {})
            if isinstance(share_data, dict):
                msg["action"] = share_data.get("action", "follow")
            self._stats["social"] += 1
        else:
            self._stats["other"] += 1

        all_messages.append(msg)
        if callback:
            callback(msg)

    def _collect_direct(self, duration: int = None, callback=None) -> list[dict]:
        """直连模式采集（简化版，不依赖douyinLive服务）"""
        # 获取直播间信息
        print("  [→] 获取直播间信息...")
        info = self._get_live_room_info()
        if info.get("status") == "error":
            print(f"  [!] 获取直播间信息失败: {info['message']}")
            print("  [→] 尝试直接连接...")

        # 连接WebSocket
        print("  [→] 连接WebSocket...")
        self._connect_websocket()

        if not self._ws:
            print("  [!] 无法建立WebSocket连接")
            return []

        # 采集循环
        self._running = True
        all_messages = []
        start_time = time.time()
        flush_interval = 3
        last_stats_time = start_time

        try:
            while self._running:
                # 时长检查
                if duration and (time.time() - start_time) > duration:
                    print(f"\n  [✓] 达到采集时长({duration}s)，停止")
                    break

                # 连接状态检查
                if self._ws and not self._ws.sock:
                    print("  [!] 连接已断开")
                    break

                # 从缓冲区取数据
                batch = []
                with self._buffer_lock:
                    if self._message_buffer:
                        batch = self._message_buffer.copy()
                        self._message_buffer.clear()

                if batch:
                    all_messages.extend(batch)
                    if callback:
                        for msg in batch:
                            callback(msg)

                # 每30秒打印一次统计
                now = time.time()
                if now - last_stats_time > 30:
                    self._print_stats()
                    last_stats_time = now

                time.sleep(flush_interval)

        except KeyboardInterrupt:
            print("\n  [!] 用户中断采集")
        finally:
            self._running = False
            if self._ws:
                self._ws.close()

        print(f"\n  采集完成！")
        print(f"  总消息数: {len(all_messages)}")
        self._print_stats()

        return all_messages

    def _connect_websocket(self):
        """直连模式：建立WebSocket连接"""
        try:
            # 构造连接URL
            ws_url = self._build_wss_url()

            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/120.0.0.0 Safari/537.36",
                "Origin": "https://live.douyin.com",
                "Sec-WebSocket-Version": "13",
            }

            cookie_str = "; ".join(f"{k}={v}" for k, v in self.cookies.items())

            self._ws = websocket.WebSocketApp(
                ws_url,
                header=headers,
                cookie=cookie_str,
                on_open=self._ws_on_open,
                on_message=self._ws_on_message,
                on_error=self._ws_on_error,
                on_close=self._ws_on_close,
            )

            ws_thread = threading.Thread(
                target=self._ws.run_forever,
                kwargs={"ping_interval": 30, "ping_timeout": 10},
                daemon=True,
            )
            ws_thread.start()
            time.sleep(2)

        except Exception as e:
            print(f"  [!] WebSocket连接失败: {e}")
            self._ws = None

    def _build_wss_url(self) -> str:
        """构造WebSocket连接URL"""
        import urllib.parse
        params = {
            "app_id": "1128",
            "room_id": self.room_id,
            "compress": "gzip",
        }
        query = urllib.parse.urlencode(params)
        return f"{self.WSS_URL_TEMPLATE}?{query}"

    def _ws_on_open(self, ws):
        print("  [✓] WebSocket连接已建立")
        # 发送初始心跳
        self._send_heartbeat(ws)

    def _ws_on_message(self, ws, message):
        """处理WebSocket消息"""
        if isinstance(message, bytes):
            self._process_binary_message(message)
        elif isinstance(message, str):
            # 心跳响应
            if message == "pong":
                return
            try:
                data = json.loads(message)
                self._process_json_message(data)
            except json.JSONDecodeError:
                pass

    def _ws_on_error(self, ws, error):
        print(f"  [!] WebSocket错误: {error}")

    def _ws_on_close(self, ws, code, msg):
        print(f"  [i] WebSocket关闭: code={code}")
        self._running = False

    def _send_heartbeat(self, ws):
        """发送心跳"""
        def heartbeat_loop():
            while self._running:
                try:
                    if ws.sock:
                        ws.send("ping")
                except Exception:
                    pass
                time.sleep(10)

        t = threading.Thread(target=heartbeat_loop, daemon=True)
        t.start()

    def _process_binary_message(self, data: bytes):
        """处理二进制消息（Protobuf + Gzip）"""
        try:
            # 尝试解压
            try:
                decompressed = gzip.decompress(data)
            except Exception:
                decompressed = data

            # 尝试提取文本信息
            text_content = decompressed.decode("utf-8", errors="ignore")

            # 从解压数据中提取关键字段
            self._extract_messages_from_bytes(text_content, decompressed)

        except Exception as e:
            pass  # 忽略解析失败的消息

    def _extract_messages_from_bytes(self, text: str, raw: bytes):
        """从解压后的数据中提取消息"""
        # 提取method字段（消息类型标识）
        methods = re.findall(r'Webcast\w+Message', text)

        # 提取用户昵称
        nicknames = re.findall(r'"nickname"\s*:\s*"([^"]{1,50})"', text)

        # 提取消息内容
        contents = re.findall(r'"content"\s*:\s*"([^"]{1,200})"', text)
        if not contents:
            contents = re.findall(r'"msg"\s*:\s*"([^"]{1,200})"', text)

        # 提取礼物信息
        gift_names = re.findall(r'"giftName"\s*:\s*"([^"]{1,50})"', text)

        # 构造消息记录
        for method in methods:
            msg_type = self.MESSAGE_TYPES.get(method, "other")

            msg = {
                "type": msg_type,
                "method": method,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "room_id": self.room_id,
            }

            if msg_type == "chat" and nicknames:
                msg["nickname"] = nicknames[0]
                msg["content"] = contents[0] if contents else ""
                # 关键词过滤
                if self.keywords:
                    if not any(kw in msg["content"] for kw in self.keywords):
                        continue
                self._stats["chat"] += 1
            elif msg_type == "gift" and nicknames:
                msg["nickname"] = nicknames[0]
                msg["gift_name"] = gift_names[0] if gift_names else ""
                self._stats["gift"] += 1
            elif msg_type == "member":
                msg["nickname"] = nicknames[0] if nicknames else ""
                # 提取在线人数
                count_match = re.search(r'"currentCount"\s*:\s*(\d+)', text)
                if count_match:
                    self._viewer_count = int(count_match.group(1))
                    msg["current_count"] = self._viewer_count
                self._stats["member"] += 1
            elif msg_type == "like":
                msg["nickname"] = nicknames[0] if nicknames else ""
                self._stats["like"] += 1
            elif msg_type == "social":
                msg["nickname"] = nicknames[0] if nicknames else ""
                msg["action"] = "follow"
                self._stats["social"] += 1
            else:
                self._stats["other"] += 1

            with self._buffer_lock:
                self._message_buffer.append(msg)

    def _process_json_message(self, data: dict):
        """处理JSON消息（来自代理服务）"""
        msg_type = data.get("type", "")
        method = data.get("method", "")

        # 系统消息
        if msg_type == "system":
            event = data.get("event", "")
            if event == "live_status":
                if not data.get("live", True):
                    print(f"  [i] {data.get('message', '直播已结束')}")
                    self._running = False
            self._stats["system"] += 1
            return

        # 业务消息
        type_name = self.MESSAGE_TYPES.get(method, "other")
        msg = {
            "type": type_name,
            "method": method,
            "timestamp": data.get("timestamp", time.strftime("%Y-%m-%d %H:%M:%S")),
            "room_id": data.get("room_id", self.room_id),
            "livename": data.get("livename", ""),
        }

        d = data.get("data", data)
        if type_name == "chat":
            msg["nickname"] = d.get("nickname", "")
            msg["content"] = d.get("content", d.get("msg", ""))
            if self.keywords:
                if not any(kw in msg.get("content", "") for kw in self.keywords):
                    return
            self._stats["chat"] += 1
        elif type_name == "gift":
            msg["nickname"] = d.get("nickname", "")
            msg["gift_name"] = d.get("gift_name", d.get("giftName", ""))
            msg["gift_count"] = d.get("gift_count", d.get("giftCount", 1))
            msg["gift_value"] = d.get("gift_value", d.get("giftValue", 0))
            self._stats["gift"] += 1
        elif type_name == "member":
            msg["nickname"] = d.get("nickname", "")
            msg["current_count"] = d.get("current_count", d.get("currentCount", 0))
            self._stats["member"] += 1
        elif type_name == "like":
            msg["nickname"] = d.get("nickname", "")
            msg["like_count"] = d.get("like_count", 1)
            self._stats["like"] += 1
        else:
            self._stats["other"] += 1

        with self._buffer_lock:
            self._message_buffer.append(msg)

    def _print_stats(self):
        """打印采集统计"""
        stats_str = " | ".join(f"{k}:{v}" for k, v in self._stats.items() if v > 0)
        viewer = f" | 在线:{self._viewer_count}" if self._viewer_count else ""
        print(f"  [📊] {stats_str}{viewer}")

    def get_stats(self) -> dict:
        return dict(self._stats)


def collect_douyin_live(room_url_or_id: str,
                        duration: int = None,
                        keywords: list = None,
                        output_path: str = None,
                        output_format: str = "xlsx") -> list[dict]:
    """
    便捷函数：采集抖音直播间数据并保存

    Args:
        room_url_or_id: 直播间URL或ID
        duration: 采集时长（秒）
        keywords: 弹幕关键词过滤
        output_path: 输出文件路径
        output_format: 输出格式 (xlsx/json/csv)

    Returns:
        采集到的消息列表
    """
    collector = DouyinLiveCollector(room_url_or_id, keywords)
    messages = collector.collect(duration=duration)

    if output_path and messages:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from engine.outputs import get_writer
        writer = get_writer(output_format)
        writer.write(messages, output_path, title="抖音直播数据")

    return messages


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="抖音直播间数据采集器")
    parser.add_argument("room", help="直播间URL或ID")
    parser.add_argument("--duration", type=int, default=300, help="采集时长(秒)，默认300")
    parser.add_argument("--keywords", help="关键词过滤，逗号分隔")
    parser.add_argument("--output", help="输出文件路径")
    parser.add_argument("--format", choices=["xlsx", "json", "csv"], default="xlsx", help="输出格式")

    args = parser.parse_args()

    keywords = [kw.strip() for kw in args.keywords.split(",")] if args.keywords else []
    output = args.output or os.path.expanduser(f"~/Desktop/抖音直播_{args.room}.xlsx")

    collect_douyin_live(
        room_url_or_id=args.room,
        duration=args.duration,
        keywords=keywords,
        output_path=output,
        output_format=args.format,
    )

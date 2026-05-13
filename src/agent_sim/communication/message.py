"""Message model for agent communication."""
from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MessageType(str, Enum):
    """消息类型枚举。"""

    DIRECT = "direct"        # 点对点消息
    BROADCAST = "broadcast"  # 广播消息
    REQUEST = "request"      # 请求消息
    RESPONSE = "response"    # 响应消息
    SYSTEM = "system"        # 系统消息


class Message(BaseModel):
    """Agent 间通信的消息模型。

    Attributes:
        sender: 发送者标识
        receiver: 接收者标识，None 表示广播
        content: 消息内容（任意类型）
        msg_type: 消息类型
        timestamp: 创建时间戳
        metadata: 附加元数据
        message_id: 唯一消息 ID
        correlation_id: 请求-响应关联 ID
    """

    sender: str
    receiver: str | None = None
    content: Any = None
    msg_type: MessageType = MessageType.BROADCAST
    timestamp: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)
    message_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    correlation_id: str | None = None

    def __str__(self) -> str:
        target = self.receiver or "ALL"
        return f"Message({self.sender} -> {target}: {self.content!r})"

    def __repr__(self) -> str:
        return (
            f"Message(sender={self.sender!r}, receiver={self.receiver!r}, "
            f"msg_type={self.msg_type.value})"
        )

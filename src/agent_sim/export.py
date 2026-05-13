"""Conversation export utilities."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_sim.communication.message import Message


def _ts_to_iso(ts: float) -> str:
    """将 unix 时间戳转为 ISO 格式字符串。"""
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _ts_to_str(ts: float) -> str:
    """将 unix 时间戳转为 HH:MM:SS 格式。"""
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%H:%M:%S")


def export_messages_to_json(
    messages: list[Message],
    output_path: str | Path,
    indent: int = 2,
) -> Path:
    """将消息列表导出为 JSON 文件。

    Args:
        messages: 消息列表
        output_path: 输出文件路径
        indent: JSON 缩进

    Returns:
        输出文件路径
    """
    path = Path(output_path)
    data = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "message_count": len(messages),
        "messages": [
            {
                "sender": msg.sender,
                "receiver": msg.receiver,
                "content": msg.content,
                "type": msg.msg_type,
                "timestamp": _ts_to_iso(msg.timestamp),
                "metadata": msg.metadata,
            }
            for msg in messages
        ],
    }
    path.write_text(json.dumps(data, indent=indent, ensure_ascii=False), encoding="utf-8")
    return path


def export_messages_to_markdown(
    messages: list[Message],
    output_path: str | Path,
    title: str = "Conversation Export",
) -> Path:
    """将消息列表导出为 Markdown 文件。

    Args:
        messages: 消息列表
        output_path: 输出文件路径
        title: 文档标题

    Returns:
        输出文件路径
    """
    path = Path(output_path)
    lines = [
        f"# {title}",
        "",
        f"Exported: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"Messages: {len(messages)}",
        "",
        "---",
        "",
    ]

    for msg in messages:
        ts = _ts_to_str(msg.timestamp)
        lines.append(f"**[{ts}] {msg.sender}** → _{msg.receiver or 'all'}_ `{msg.msg_type}`")
        lines.append("")
        lines.append(f"> {msg.content}")
        if msg.metadata:
            lines.append(f"> _metadata: {json.dumps(msg.metadata, ensure_ascii=False)}_")
        lines.append("")
        lines.append("---")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def format_conversation_table(messages: list[Message]) -> str:
    """将消息格式化为终端表格。

    Args:
        messages: 消息列表

    Returns:
        格式化的表格字符串
    """
    if not messages:
        return "(无消息)"

    # 计算列宽
    headers = ["Time", "From", "To", "Type", "Content"]
    rows = []
    for msg in messages:
        ts = _ts_to_str(msg.timestamp)
        content = msg.content[:60] + "..." if len(msg.content) > 60 else msg.content
        rows.append([ts, msg.sender, msg.receiver or "all", msg.msg_type, content])

    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def fmt_row(cells: list[str]) -> str:
        return " | ".join(cell.ljust(widths[i]) for i, cell in enumerate(cells))

    lines = [
        fmt_row(headers),
        "-+-".join("-" * w for w in widths),
    ]
    for row in rows:
        lines.append(fmt_row(row))

    return "\n".join(lines)


def export_messages_to_csv(
    messages: list[Message],
    output_path: str | Path,
) -> Path:
    """将消息列表导出为 CSV 文件。

    Args:
        messages: 消息列表
        output_path: 输出文件路径

    Returns:
        输出文件路径
    """
    import csv

    path = Path(output_path)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "sender", "receiver", "type", "content", "correlation_id"])
        for msg in messages:
            writer.writerow([
                _ts_to_iso(msg.timestamp),
                msg.sender,
                msg.receiver or "",
                msg.msg_type,
                msg.content,
                msg.correlation_id or "",
            ])
    return path

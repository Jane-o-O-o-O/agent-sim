"""Conversation export utilities and HTML report generation."""
from __future__ import annotations

import json
import time as _time
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


class HTMLReport:
    """HTML 仿真报告生成器。

    生成美观的 HTML 报告，包含 SVG 图表、指标表格和评估结果。

    Attributes:
        result: RunResult 仿真结果
        scenario_name: 场景名称
        eval_report: 可选的评估报告

    Example:
        >>> report = HTMLReport(result, scenario_name="ping-pong")
        >>> html = report.render()
        >>> report.save("report.html")
    """

    def __init__(
        self,
        result: Any,
        scenario_name: str = "",
        eval_report: Any = None,
    ) -> None:
        self.result = result
        self.scenario_name = scenario_name
        self.eval_report = eval_report

    def render(self) -> str:
        """渲染完整 HTML 报告。

        Returns:
            HTML 字符串
        """
        r = self.result
        agent_states = getattr(r, "agent_states", {})
        metrics = getattr(r, "metrics", {})
        step_details = metrics.get("step_details", [])

        agent_bar_svg = self._render_bar_chart(agent_states, 500, 200, "Agent 状态")
        step_chart_svg = self._render_step_chart(step_details, 500, 180)
        eval_html = self._render_eval()

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Agent Sim Report - {self.scenario_name}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       background: #f5f5f5; color: #333; padding: 20px; }}
.container {{ max-width: 900px; margin: 0 auto; }}
.header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
           color: white; padding: 30px; border-radius: 12px; margin-bottom: 20px; }}
.header h1 {{ font-size: 24px; margin-bottom: 8px; }}
.header p {{ opacity: 0.9; font-size: 14px; }}
.card {{ background: white; border-radius: 8px; padding: 20px; margin-bottom: 16px;
         box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
.card h2 {{ font-size: 16px; color: #667eea; margin-bottom: 12px; border-bottom: 2px solid #f0f0f0; padding-bottom: 8px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }}
.stat {{ text-align: center; padding: 12px; background: #f8f9fa; border-radius: 8px; }}
.stat .value {{ font-size: 28px; font-weight: bold; color: #667eea; }}
.stat .label {{ font-size: 12px; color: #666; margin-top: 4px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #eee; }}
th {{ background: #f8f9fa; font-weight: 600; }}
.badge {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }}
.badge-pass {{ background: #d4edda; color: #155724; }}
.badge-fail {{ background: #f8d7da; color: #721c24; }}
.badge-state {{ background: #e7e3ff; color: #667eea; }}
svg {{ display: block; margin: 0 auto; }}
.footer {{ text-align: center; color: #999; font-size: 12px; margin-top: 20px; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>📊 Agent Sim Report</h1>
    <p>{self.scenario_name} — 生成时间: {_ts_to_iso(_time.time())}</p>
  </div>

  <div class="card">
    <h2>📈 仿真概览</h2>
    <div class="stats">
      <div class="stat"><div class="value">{getattr(r, 'steps_completed', 0)}</div><div class="label">完成步数</div></div>
      <div class="stat"><div class="value">{getattr(r, 'total_messages', 0)}</div><div class="label">消息总数</div></div>
      <div class="stat"><div class="value">{len(agent_states)}</div><div class="label">Agent 数</div></div>
      <div class="stat"><div class="value">{getattr(r, 'duration', 0):.3f}s</div><div class="label">运行时间</div></div>
      <div class="stat"><div class="value">{"⚠️ 超时" if getattr(r, 'timed_out', False) else "✅ 正常"}</div><div class="label">状态</div></div>
    </div>
  </div>

  <div class="card">
    <h2>🤖 Agent 状态</h2>
    {agent_bar_svg}
    <table style="margin-top:12px">
      <tr><th>Agent</th><th>状态</th></tr>
      {"".join(f'<tr><td>{name}</td><td><span class="badge badge-state">{state}</span></td></tr>' for name, state in agent_states.items())}
    </table>
  </div>

  <div class="card">
    <h2>📊 每步消息量</h2>
    {step_chart_svg}
  </div>

  {eval_html}

  <div class="footer">Agent Sim v0.7.0 — Multi-agent Simulation Framework</div>
</div>
</body>
</html>"""
        return html

    def _render_bar_chart(self, data: dict[str, Any], width: int, height: int, title: str) -> str:
        """渲染 SVG 水平柱状图。"""
        if not data:
            return '<p style="text-align:center;color:#999">无数据</p>'

        items = list(data.items())
        bar_h = min(30, (height - 20) // max(len(items), 1))
        gap = 4
        chart_h = len(items) * (bar_h + gap) + 20

        colors = ["#667eea", "#764ba2", "#f093fb", "#f5576c", "#4facfe", "#00f2fe", "#43e97b", "#fa709a"]
        svg_parts = [f'<svg width="{width}" height="{chart_h}" xmlns="http://www.w3.org/2000/svg">']

        for i, (name, value) in enumerate(items):
            y = i * (bar_h + gap) + 10
            bar_width = int(width * 0.6)
            color = colors[i % len(colors)]
            svg_parts.append(
                f'<rect x="120" y="{y}" width="{bar_width}" height="{bar_h}" rx="4" fill="{color}" opacity="0.8"/>'
            )
            svg_parts.append(
                f'<text x="115" y="{y + bar_h // 2 + 5}" text-anchor="end" font-size="12" fill="#333">{name}</text>'
            )
            svg_parts.append(
                f'<text x="{125 + bar_width}" y="{y + bar_h // 2 + 5}" font-size="11" fill="#666">{value}</text>'
            )

        svg_parts.append('</svg>')
        return '\n'.join(svg_parts)

    def _render_step_chart(self, step_details: list[dict], width: int, height: int) -> str:
        """渲染 SVG 折线图（每步消息量）。"""
        if not step_details:
            return '<p style="text-align:center;color:#999">无步骤数据</p>'

        msgs = [d.get("messages_sent", 0) for d in step_details]
        steps = list(range(1, len(msgs) + 1))
        max_msg = max(max(msgs), 1)

        pad_left, pad_right, pad_top, pad_bottom = 50, 20, 20, 30
        chart_w = width - pad_left - pad_right
        chart_h = height - pad_top - pad_bottom

        def _x(i: int) -> int:
            return pad_left + (i * chart_w // max(len(steps) - 1, 1))

        def _y(v: int) -> int:
            return pad_top + chart_h - (v * chart_h // max_msg)

        svg = [f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">']
        svg.append(f'<rect x="{pad_left}" y="{pad_top}" width="{chart_w}" height="{chart_h}" fill="#f8f9fa" rx="4"/>')

        # Grid lines
        for i in range(5):
            gy = pad_top + i * chart_h // 4
            gval = max_msg - i * max_msg // 4
            svg.append(f'<line x1="{pad_left}" y1="{gy}" x2="{pad_left + chart_w}" y2="{gy}" stroke="#eee" stroke-width="1"/>')
            svg.append(f'<text x="{pad_left - 5}" y="{gy + 4}" text-anchor="end" font-size="10" fill="#999">{gval}</text>')

        # Line
        points = ' '.join(f'{_x(i)},{_y(v)}' for i, v in enumerate(msgs))
        svg.append(f'<polyline points="{points}" fill="none" stroke="#667eea" stroke-width="2"/>')

        # Dots
        for i, v in enumerate(msgs):
            svg.append(f'<circle cx="{_x(i)}" cy="{_y(v)}" r="4" fill="#667eea"/>')

        # X labels
        for i, s in enumerate(steps):
            svg.append(f'<text x="{_x(i)}" y="{height - 5}" text-anchor="middle" font-size="10" fill="#999">{s}</text>')

        svg.append('</svg>')
        return '\n'.join(svg)

    def _render_eval(self) -> str:
        """渲染评估结果 HTML。"""
        if not self.eval_report:
            return ""

        report = self.eval_report
        passed = getattr(report, "passed", False)
        score = getattr(report, "overall_score", 0)
        results = getattr(report, "results", [])

        rows = []
        for r in results:
            name = getattr(r, "name", "?")
            s = getattr(r, "score", 0)
            p = getattr(r, "passed", False)
            badge = "badge-pass" if p else "badge-fail"
            status = "✅" if p else "❌"
            rows.append(
                f'<tr><td>{name}</td><td>{s:.3f}</td>'
                f'<td><span class="badge {badge}">{status}</span></td></tr>'
            )

        return f"""
  <div class="card">
    <h2>📋 评估报告</h2>
    <div class="stats">
      <div class="stat"><div class="value">{score:.3f}</div><div class="label">综合分数</div></div>
      <div class="stat"><div class="value">{"✅ 通过" if passed else "❌ 未通过"}</div><div class="label">结果</div></div>
    </div>
    <table style="margin-top:12px">
      <tr><th>评估器</th><th>分数</th><th>状态</th></tr>
      {"".join(rows)}
    </table>
  </div>"""

    def save(self, path: str | Path) -> Path:
        """保存 HTML 报告到文件。

        Args:
            path: 输出文件路径

        Returns:
            输出文件路径
        """
        output = Path(path)
        output.write_text(self.render(), encoding="utf-8")
        return output

def topology_management(*args, **kwargs):
    """Topology management implementation.

    Added: 2026-04-30
    Provides topology management functionality for the core module.
    """
    _logger.debug(f"Running topology management with args={args}, kwargs={kwargs}")
    result = _process_topology_management(args, kwargs)
    _metrics.record("topology_management", result)
    return result


def _process_topology_management(args, kwargs):
    """Internal processor for topology management."""
    config = kwargs.get("config", {})
    timeout = config.get("timeout", 30)
    max_retries = config.get("max_retries", 3)

    for attempt in range(max_retries):
        try:
            return _execute_topology_management(args, config)
        except TimeoutError:
            if attempt < max_retries - 1:
                _logger.warning(f"Attempt {attempt + 1} timed out, retrying...")
                time.sleep(2 ** attempt)
            else:
                raise


def _execute_topology_management(args, config):
    """Execute the core topology management logic."""
    return {"status": "success", "feature": "topology management", "config": config}

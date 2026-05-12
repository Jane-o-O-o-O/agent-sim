"""ASCII chart rendering for terminal visualization."""
from __future__ import annotations


def bar_chart(
    data: dict[str, float],
    title: str = "",
    width: int = 40,
    show_values: bool = True,
    char: str = "█",
    color: bool = False,
) -> str:
    """生成 ASCII 水平柱状图。

    Args:
        data: {标签: 数值} 字典
        title: 图表标题
        width: 柱状图最大宽度（字符数）
        show_values: 是否显示数值
        char: 柱状图字符
        color: 是否使用 ANSI 颜色

    Returns:
        ASCII 柱状图字符串

    Example:
        >>> print(bar_chart({"A": 10, "B": 25, "C": 15}))
    """
    if not data:
        return "(no data)"

    max_val = max(data.values())
    max_label_len = max(len(str(k)) for k in data) if data else 0

    lines = []
    if title:
        lines.append(title)
        lines.append("─" * (max_label_len + width + 10))
        lines.append("")

    colors = ["\033[36m", "\033[33m", "\033[32m", "\033[35m", "\033[34m", "\033[31m"]
    reset = "\033[0m"

    for i, (label, value) in enumerate(data.items()):
        label_str = str(label).ljust(max_label_len)
        if max_val > 0:
            bar_len = int((value / max_val) * width)
        else:
            bar_len = 0
        bar = char * bar_len

        if color:
            c = colors[i % len(colors)]
            bar = f"{c}{bar}{reset}"

        val_str = f" {value:.1f}" if show_values else ""
        lines.append(f"{label_str} │{bar}{val_str}")

    return "\n".join(lines)


def line_chart(
    data: list[float],
    title: str = "",
    width: int = 60,
    height: int = 10,
    y_label: str = "",
    x_label: str = "",
) -> str:
    """生成 ASCII 折线图。

    Args:
        data: 数值序列
        title: 图表标题
        width: 图表宽度
        height: 图表高度（行数）
        y_label: Y 轴标签
        x_label: X 轴标签

    Returns:
        ASCII 折线图字符串
    """
    if not data:
        return "(no data)"

    min_val = min(data)
    max_val = max(data)
    val_range = max_val - min_val if max_val != min_val else 1

    # 采样数据到 width 个点
    if len(data) > width:
        step = len(data) / width
        sampled = [data[int(i * step)] for i in range(width)]
    else:
        sampled = list(data)

    lines = []
    if title:
        lines.append(title)
        lines.append("")

    # 构建图表网格
    grid = [[" " for _ in range(len(sampled))] for _ in range(height)]

    for col, val in enumerate(sampled):
        row = int(((val - min_val) / val_range) * (height - 1))
        row = height - 1 - row  # 翻转 Y 轴
        grid[row][col] = "●"

    # Y 轴标签宽度
    y_width = max(len(f"{max_val:.1f}"), len(f"{min_val:.1f}"), len(y_label))

    # 渲染
    for row_idx, row in enumerate(grid):
        if row_idx == 0:
            label = f"{max_val:.1f}".rjust(y_width)
        elif row_idx == height - 1:
            label = f"{min_val:.1f}".rjust(y_width)
        elif row_idx == height // 2:
            mid_val = (max_val + min_val) / 2
            label = f"{mid_val:.1f}".rjust(y_width)
        else:
            label = " " * y_width

        lines.append(f"{label} │{''.join(row)}")

    # X 轴
    lines.append(" " * y_width + " └" + "─" * len(sampled))

    if x_label:
        lines.append(" " * (y_width + 2) + x_label)

    return "\n".join(lines)


def sparkline(data: list[float], width: int = 40) -> str:
    """生成 Unicode 迷你折线图（sparkline）。

    使用 Unicode Block 和 Braille 字符在单行内显示数据趋势。

    Args:
        data: 数值序列
        width: 输出宽度

    Returns:
        单行 sparkline 字符串

    Example:
        >>> sparkline([1, 5, 3, 8, 4, 7, 2])
        "▁▅▂█▃▆▁"
    """
    if not data:
        return ""

    # 采样
    if len(data) > width:
        step = len(data) / width
        sampled = [data[int(i * step)] for i in range(width)]
    else:
        sampled = list(data)

    min_val = min(sampled)
    max_val = max(sampled)
    val_range = max_val - min_val if max_val != min_val else 1

    # Unicode block 字符（从低到高）
    blocks = "▁▂▃▄▅▆▇█"

    result = []
    for val in sampled:
        idx = int(((val - min_val) / val_range) * (len(blocks) - 1))
        result.append(blocks[idx])

    return "".join(result)


def metrics_table(
    step_data: list[dict[str, float | int]],
    columns: list[str] | None = None,
    title: str = "",
) -> str:
    """生成指标数据表格。

    Args:
        step_data: 步骤数据列表
        columns: 要显示的列名（None 显示全部）
        title: 表格标题

    Returns:
        ASCII 表格字符串
    """
    if not step_data:
        return "(no data)"

    if columns is None:
        columns = list(step_data[0].keys())

    # 计算列宽
    widths = {col: len(str(col)) for col in columns}
    for row in step_data:
        for col in columns:
            val = row.get(col, "")
            widths[col] = max(widths[col], len(f"{val}"))

    lines = []
    if title:
        lines.append(title)
        lines.append("")

    # 表头
    header = " | ".join(str(col).ljust(widths[col]) for col in columns)
    lines.append(header)
    lines.append("-+-".join("-" * widths[col] for col in columns))

    # 数据行
    for row in step_data:
        cells = []
        for col in columns:
            val = row.get(col, "")
            if isinstance(val, float):
                cells.append(f"{val:.2f}".rjust(widths[col]))
            else:
                cells.append(str(val).ljust(widths[col]))
        lines.append(" | ".join(cells))

    return "\n".join(lines)

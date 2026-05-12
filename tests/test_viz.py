"""Tests for visualization module."""
from __future__ import annotations

from agent_sim.viz.charts import bar_chart, line_chart, metrics_table, sparkline


class TestBarChart:
    """bar_chart 测试。"""

    def test_basic(self) -> None:
        data = {"A": 10, "B": 20, "C": 15}
        result = bar_chart(data)
        assert "A" in result
        assert "B" in result
        assert "10.0" in result

    def test_empty_data(self) -> None:
        assert bar_chart({}) == "(no data)"

    def test_with_title(self) -> None:
        result = bar_chart({"A": 1}, title="Test Chart")
        assert "Test Chart" in result

    def test_show_values_false(self) -> None:
        result = bar_chart({"A": 10}, show_values=False)
        assert "10.0" not in result

    def test_custom_char(self) -> None:
        result = bar_chart({"A": 10}, char="#")
        assert "#" in result

    def test_width(self) -> None:
        result = bar_chart({"A": 100, "B": 50}, width=20)
        assert "A" in result

    def test_color(self) -> None:
        result = bar_chart({"A": 10}, color=True)
        assert "\033[" in result  # ANSI escape

    def test_zero_values(self) -> None:
        result = bar_chart({"A": 0, "B": 0})
        assert "A" in result


class TestLineChart:
    """line_chart 测试。"""

    def test_basic(self) -> None:
        data = [1, 5, 3, 8, 4, 7, 2, 9, 6]
        result = line_chart(data)
        assert "●" in result

    def test_empty_data(self) -> None:
        assert line_chart([]) == "(no data)"

    def test_with_title(self) -> None:
        result = line_chart([1, 2, 3], title="My Chart")
        assert "My Chart" in result

    def test_with_labels(self) -> None:
        result = line_chart([1, 2, 3, 4, 5], y_label="count", x_label="step")
        assert "step" in result  # x_label at bottom

    def test_single_value(self) -> None:
        result = line_chart([5, 5, 5])
        assert "●" in result

    def test_sampling(self) -> None:
        data = list(range(100))
        result = line_chart(data, width=10)
        assert "●" in result

    def test_height(self) -> None:
        result = line_chart([1, 2, 3], height=5)
        lines = result.strip().split("\n")
        # At least height + axis lines
        assert len(lines) >= 5


class TestSparkline:
    """sparkline 测试。"""

    def test_basic(self) -> None:
        result = sparkline([1, 5, 3, 8, 4, 7, 2])
        assert len(result) == 7
        # Should use block characters
        blocks = set("▁▂▃▄▅▆▇█")
        assert all(c in blocks for c in result)

    def test_empty(self) -> None:
        assert sparkline([]) == ""

    def test_same_values(self) -> None:
        result = sparkline([5, 5, 5, 5])
        assert len(result) == 4

    def test_increasing(self) -> None:
        result = sparkline([1, 2, 3, 4, 5])
        # Should show increasing blocks
        assert result[0] == "▁"
        assert result[-1] == "█"

    def test_width_limit(self) -> None:
        data = list(range(100))
        result = sparkline(data, width=10)
        assert len(result) == 10


class TestMetricsTable:
    """metrics_table 测试。"""

    def test_basic(self) -> None:
        data = [
            {"step": 1, "messages": 5, "agents": 3},
            {"step": 2, "messages": 8, "agents": 3},
        ]
        result = metrics_table(data)
        assert "step" in result
        assert "messages" in result
        assert "5" in result  # integers displayed as-is

    def test_empty(self) -> None:
        assert metrics_table([]) == "(no data)"

    def test_with_title(self) -> None:
        data = [{"step": 1}]
        result = metrics_table(data, title="Steps")
        assert "Steps" in result

    def test_column_filter(self) -> None:
        data = [{"step": 1, "messages": 5, "agents": 3}]
        result = metrics_table(data, columns=["step", "messages"])
        assert "step" in result
        assert "messages" in result
        assert "agents" not in result

    def test_float_formatting(self) -> None:
        data = [{"value": 3.14159}]
        result = metrics_table(data)
        assert "3.14" in result

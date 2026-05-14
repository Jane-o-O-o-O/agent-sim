"""Advanced metrics aggregation with percentiles, histograms, and trends."""
from __future__ import annotations

import logging
import math
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class PercentileResult(BaseModel):
    """百分位数结果。

    Attributes:
        p50: 中位数
        p90: 90th 百分位
        p95: 95th 百分位
        p99: 99th 百分位
        min_val: 最小值
        max_val: 最大值
        mean: 平均值
        count: 样本数
    """

    p50: float = 0.0
    p90: float = 0.0
    p95: float = 0.0
    p99: float = 0.0
    min_val: float = 0.0
    max_val: float = 0.0
    mean: float = 0.0
    count: int = 0


class HistogramBin(BaseModel):
    """直方图区间。

    Attributes:
        lower: 下界
        upper: 上界
        count: 计数
        frequency: 频率
    """

    lower: float = 0.0
    upper: float = 0.0
    count: int = 0
    frequency: float = 0.0


class TrendDirection(BaseModel):
    """趋势方向。

    Attributes:
        direction: 趋势方向 (up/down/stable)
        slope: 斜率
        r_squared: R² 决定系数
        description: 描述
    """

    direction: str = "stable"
    slope: float = 0.0
    r_squared: float = 0.0
    description: str = ""


class MetricAggregator:
    """高级指标聚合器。

    提供百分位数计算、直方图生成、趋势分析等高级统计功能。

    Example:
        >>> agg = MetricAggregator()
        >>> pct = agg.percentiles([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        >>> print(pct.p50, pct.p95)
        >>> hist = agg.histogram([1, 2, 2, 3, 3, 3, 4, 5], bins=5)
        >>> trend = agg.trend([10, 20, 30, 40, 50])
    """

    @staticmethod
    def percentiles(values: list[float]) -> PercentileResult:
        """计算百分位数。

        Args:
            values: 数值列表

        Returns:
            百分位数结果
        """
        if not values:
            return PercentileResult()

        sorted_vals = sorted(values)
        n = len(sorted_vals)

        def _percentile(p: float) -> float:
            """计算第 p 百分位。"""
            if n == 1:
                return sorted_vals[0]
            k = (n - 1) * p / 100.0
            f = math.floor(k)
            c = math.ceil(k)
            if f == c:
                return sorted_vals[int(k)]
            return sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f)

        return PercentileResult(
            p50=_percentile(50),
            p90=_percentile(90),
            p95=_percentile(95),
            p99=_percentile(99),
            min_val=sorted_vals[0],
            max_val=sorted_vals[-1],
            mean=sum(sorted_vals) / n,
            count=n,
        )

    @staticmethod
    def histogram(
        values: list[float], bins: int = 10,
    ) -> list[HistogramBin]:
        """生成直方图。

        Args:
            values: 数值列表
            bins: 区间数

        Returns:
            直方图区间列表
        """
        if not values or bins <= 0:
            return []

        min_val = min(values)
        max_val = max(values)

        if min_val == max_val:
            return [HistogramBin(
                lower=min_val, upper=max_val + 1,
                count=len(values), frequency=1.0,
            )]

        bin_width = (max_val - min_val) / bins
        result: list[HistogramBin] = []

        for i in range(bins):
            lower = min_val + i * bin_width
            upper = lower + bin_width
            count = sum(1 for v in values if lower <= v < upper)
            # 最后一个 bin 包含上界
            if i == bins - 1:
                count = sum(1 for v in values if lower <= v <= upper)
            result.append(HistogramBin(
                lower=round(lower, 4),
                upper=round(upper, 4),
                count=count,
                frequency=round(count / len(values), 4),
            ))

        return result

    @staticmethod
    def trend(values: list[float]) -> TrendDirection:
        """分析时间序列趋势（线性回归）。

        Args:
            values: 按时间顺序的数值列表

        Returns:
            趋势方向
        """
        n = len(values)
        if n < 2:
            return TrendDirection(direction="stable", description="数据不足")

        x = list(range(n))
        x_mean = sum(x) / n
        y_mean = sum(values) / n

        # 计算线性回归
        ss_xy = sum((x[i] - x_mean) * (values[i] - y_mean) for i in range(n))
        ss_xx = sum((x[i] - x_mean) ** 2 for i in range(n))
        ss_yy = sum((values[i] - y_mean) ** 2 for i in range(n))

        if ss_xx == 0:
            return TrendDirection(direction="stable", description="X 方差为零")

        slope = ss_xy / ss_xx

        # R² 决定系数
        r_squared = (ss_xy ** 2) / (ss_xx * ss_yy) if ss_yy > 0 else 0.0

        # 判断趋势方向
        if abs(slope) < y_mean * 0.01 if y_mean != 0 else abs(slope) < 0.01:
            direction = "stable"
            desc = "趋势稳定"
        elif slope > 0:
            direction = "up"
            desc = f"上升趋势 (斜率={slope:.4f})"
        else:
            direction = "down"
            desc = f"下降趋势 (斜率={slope:.4f})"

        return TrendDirection(
            direction=direction, slope=slope, r_squared=r_squared, description=desc,
        )

    @staticmethod
    def moving_average(values: list[float], window: int = 3) -> list[float]:
        """计算移动平均。

        Args:
            values: 数值列表
            window: 窗口大小

        Returns:
            移动平均列表
        """
        if not values or window <= 0:
            return []
        result = []
        for i in range(len(values)):
            start = max(0, i - window + 1)
            window_vals = values[start:i + 1]
            result.append(sum(window_vals) / len(window_vals))
        return result

    @staticmethod
    def std_dev(values: list[float]) -> float:
        """计算标准差。

        Args:
            values: 数值列表

        Returns:
            标准差
        """
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
        return math.sqrt(variance)

    @staticmethod
    def outliers(values: list[float], factor: float = 1.5) -> list[float]:
        """检测异常值（IQR 方法）。

        Args:
            values: 数值列表
            factor: IQR 倍数（默认 1.5）

        Returns:
            异常值列表
        """
        if len(values) < 4:
            return []

        sorted_vals = sorted(values)
        n = len(sorted_vals)
        q1 = sorted_vals[n // 4]
        q3 = sorted_vals[3 * n // 4]
        iqr = q3 - q1
        lower = q1 - factor * iqr
        upper = q3 + factor * iqr
        return [v for v in values if v < lower or v > upper]

    def aggregate_step_metrics(
        self, step_details: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """聚合步骤指标。

        Args:
            step_details: 步骤详情列表

        Returns:
            聚合后的指标
        """
        if not step_details:
            return {}

        messages = [d.get("messages_sent", 0) for d in step_details]
        active = [d.get("agents_active", 0) for d in step_details]

        msg_pct = self.percentiles(messages)
        active_pct = self.percentiles(active)
        msg_trend = self.trend(messages)

        return {
            "messages": {
                "percentiles": msg_pct.model_dump(),
                "trend": msg_trend.model_dump(),
                "std_dev": round(self.std_dev(messages), 3),
                "moving_avg": [round(v, 2) for v in self.moving_average(messages, 3)],
            },
            "agents_active": {
                "percentiles": active_pct.model_dump(),
                "std_dev": round(self.std_dev(active), 3),
            },
            "outlier_steps": [
                d.get("step") for d in step_details
                if d.get("messages_sent", 0) in self.outliers(messages)
            ],
        }

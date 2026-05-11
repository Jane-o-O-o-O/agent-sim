"""Logging configuration for the agent-sim framework."""
from __future__ import annotations

import logging
import sys
from typing import TextIO


def setup_logging(
    level: int | str = logging.INFO,
    stream: TextIO | None = None,
    fmt: str | None = None,
) -> None:
    """配置框架日志。

    Args:
        level: 日志级别
        stream: 输出流，默认 stderr
        fmt: 日志格式字符串
    """
    if fmt is None:
        fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(logging.Formatter(fmt, datefmt="%H:%M:%S"))

    root = logging.getLogger("agent_sim")
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """获取 agent-sim 子模块 logger。

    Args:
        name: 模块名 (如 "agent", "communication")

    Returns:
        logging.Logger 实例
    """
    return logging.getLogger(f"agent_sim.{name}")

"""Tests for logging configuration."""
import logging

from agent_sim.log import get_logger, setup_logging


class TestLogging:
    """Test logging setup."""

    def test_setup_logging_default(self) -> None:
        """默认日志配置。"""
        setup_logging()
        logger = logging.getLogger("agent_sim")
        assert logger.level == logging.INFO
        assert len(logger.handlers) >= 1

    def test_setup_logging_debug(self) -> None:
        """Debug 级别。"""
        setup_logging(level=logging.DEBUG)
        logger = logging.getLogger("agent_sim")
        assert logger.level == logging.DEBUG

    def test_setup_logging_custom_stream(self) -> None:
        """自定义输出流。"""
        import io
        stream = io.StringIO()
        setup_logging(level=logging.DEBUG, stream=stream)

        logger = get_logger("test")
        logger.debug("test message")

        output = stream.getvalue()
        assert "test message" in output

    def test_get_logger(self) -> None:
        """获取子模块 logger。"""
        logger = get_logger("agent")
        assert logger.name == "agent_sim.agent"

    def test_get_logger_nested(self) -> None:
        """获取嵌套 logger。"""
        logger = get_logger("scenario.runner")
        assert logger.name == "agent_sim.scenario.runner"

    def test_setup_logging_custom_format(self) -> None:
        """自定义格式。"""
        import io
        stream = io.StringIO()
        setup_logging(level=logging.INFO, stream=stream, fmt="%(message)s")

        logger = get_logger("test")
        logger.info("hello")

        output = stream.getvalue()
        assert output.strip() == "hello"

    def test_setup_logging_clears_handlers(self) -> None:
        """重复调用清除旧 handler。"""
        setup_logging()
        setup_logging()
        logger = logging.getLogger("agent_sim")
        # 只应有一个 handler
        assert len(logger.handlers) == 1

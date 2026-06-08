# tests/unit/utils/test_logger.py
"""Unit tests for structured logging utility."""

from __future__ import annotations

import logging

from app.utils.logger import get_logger


class TestGetLogger:
    """Logger factory behavior."""

    def test_returns_logger_instance(self) -> None:
        logger = get_logger("test_module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_module"

    def test_idempotent_handlers(self) -> None:
        """Calling twice does not duplicate handlers."""
        logger = get_logger("test_idempotent")
        first_count = len(logger.handlers)
        logger2 = get_logger("test_idempotent")
        assert len(logger2.handlers) == first_count

    def test_level_set(self) -> None:
        logger = get_logger("test_level", level=logging.DEBUG)
        assert logger.level == logging.DEBUG
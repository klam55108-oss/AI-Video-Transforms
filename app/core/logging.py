"""
Custom logging filters and configuration.

Provides logging utilities for filtering benign errors and
configuring application-wide logging behavior.
"""

from __future__ import annotations

import logging


class ExitCodeFilter(logging.Filter):
    """Filter out benign subprocess exit errors during shutdown."""

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Filter log records containing benign exit codes.

        Args:
            record: The log record to filter

        Returns:
            False if the record should be filtered out, True otherwise
        """
        # Suppress "Command failed with exit code -2" (SIGINT) from SDK
        return "exit code -2" not in record.getMessage()

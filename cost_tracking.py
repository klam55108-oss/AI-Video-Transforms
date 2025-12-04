"""
Cost tracking dataclasses for Claude Agent SDK usage.

This module provides data structures for tracking token usage and calculating
costs for Claude API calls, with support for deduplication by message ID.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class UsageData:
    """
    Token usage data from a single Claude API message.

    Attributes:
        message_id: Unique message identifier for deduplication
        input_tokens: Regular input tokens consumed
        output_tokens: Output tokens generated
        cache_creation_input_tokens: Tokens used for cache creation
        cache_read_input_tokens: Tokens read from cache (cheaper)
    """

    message_id: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


@dataclass
class SessionCost:
    """
    Aggregated cost tracking for a Claude Agent SDK session.

    Uses message ID deduplication to prevent counting the same usage data
    multiple times when streaming messages. Cost is tracked using the SDK's
    authoritative total_cost_usd rather than manual calculation.

    Note on precision: Cost is stored as float since the SDK provides float.
    For typical session costs ($0.01-$100), float precision is adequate.
    If sub-cent precision becomes critical, consider Decimal or integer cents.

    Attributes:
        session_id: UUID of the session
        total_input_tokens: Cumulative input tokens
        total_output_tokens: Cumulative output tokens
        total_cache_creation_tokens: Cumulative cache creation tokens
        total_cache_read_tokens: Cumulative cache read tokens
        reported_cost_usd: SDK-reported cumulative cost (updates with each ResultMessage)
        processed_ids: Set of message IDs already processed (deduplication)
    """

    session_id: str
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_creation_tokens: int = 0
    total_cache_read_tokens: int = 0
    reported_cost_usd: float = 0.0  # SDK's cumulative cost, updated per ResultMessage
    processed_ids: set[str] = field(default_factory=set)

    def add_usage(self, usage: UsageData) -> bool:
        """
        Add usage data to the session cost tracker.

        Deduplicates by message ID - if this message has already been
        processed, returns False without updating totals.

        Args:
            usage: UsageData from a single message

        Returns:
            True if usage was added, False if it was a duplicate
        """
        if usage.message_id in self.processed_ids:
            return False

        self.processed_ids.add(usage.message_id)
        self.total_input_tokens += usage.input_tokens
        self.total_output_tokens += usage.output_tokens
        self.total_cache_creation_tokens += usage.cache_creation_input_tokens
        self.total_cache_read_tokens += usage.cache_read_input_tokens
        return True

    def set_reported_cost(self, cost: float) -> None:
        """
        Set the SDK-reported cumulative session cost.

        The SDK provides total_cost_usd on ResultMessage which represents the
        CUMULATIVE cost for the entire session (not per-message). Each call
        to this method overwrites the previous value with the latest cumulative
        total from the SDK, which is model-aware and API-calculated.

        Args:
            cost: The cumulative total_cost_usd from SDK ResultMessage
        """
        self.reported_cost_usd = cost

    def to_dict(self) -> dict[str, str | int | float | list[str]]:
        """
        Convert to dictionary for JSON serialization.

        Returns:
            Dictionary with all cost tracking data
        """
        return {
            "session_id": self.session_id,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cache_creation_tokens": self.total_cache_creation_tokens,
            "total_cache_read_tokens": self.total_cache_read_tokens,
            "total_cost_usd": self.reported_cost_usd,
            "processed_message_ids": list(self.processed_ids),
        }

    @classmethod
    def from_dict(cls, data: dict) -> SessionCost:
        """
        Reconstruct SessionCost from dictionary.

        Args:
            data: Dictionary from to_dict() or storage

        Returns:
            SessionCost instance
        """
        return cls(
            session_id=data["session_id"],
            total_input_tokens=data.get("total_input_tokens", 0),
            total_output_tokens=data.get("total_output_tokens", 0),
            total_cache_creation_tokens=data.get("total_cache_creation_tokens", 0),
            total_cache_read_tokens=data.get("total_cache_read_tokens", 0),
            reported_cost_usd=data.get("total_cost_usd", 0.0),
            processed_ids=set(data.get("processed_message_ids", [])),
        )

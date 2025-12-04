"""
Tests for cost tracking functionality.

This module tests the cost tracking system for monitoring token usage
and API costs across agent sessions.
"""

from __future__ import annotations


class TestUsageData:
    """Test UsageData dataclass creation and validation."""

    def test_usage_data_creation(self):
        """Test creating UsageData with all fields."""
        from app.core.cost_tracking import UsageData

        usage = UsageData(
            message_id="msg_123",
            input_tokens=1500,
            output_tokens=500,
            cache_creation_input_tokens=200,
            cache_read_input_tokens=1000,
        )

        assert usage.message_id == "msg_123"
        assert usage.input_tokens == 1500
        assert usage.output_tokens == 500
        assert usage.cache_creation_input_tokens == 200
        assert usage.cache_read_input_tokens == 1000

    def test_usage_data_defaults(self):
        """Test that UsageData uses default values for optional fields."""
        from app.core.cost_tracking import UsageData

        usage = UsageData(message_id="msg_456")

        assert usage.message_id == "msg_456"
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0
        assert usage.cache_creation_input_tokens == 0
        assert usage.cache_read_input_tokens == 0


class TestSessionCost:
    """Test SessionCost tracking and aggregation."""

    def test_add_usage_success(self):
        """Test adding usage data to a session."""
        from app.core.cost_tracking import SessionCost, UsageData

        session_cost = SessionCost(session_id="test-session")
        usage = UsageData(
            message_id="msg_001",
            input_tokens=100,
            output_tokens=50,
        )

        result = session_cost.add_usage(usage)

        assert result is True
        assert session_cost.total_input_tokens == 100
        assert session_cost.total_output_tokens == 50
        assert "msg_001" in session_cost.processed_ids

    def test_add_usage_deduplication(self):
        """Test that duplicate message IDs are not counted twice."""
        from app.core.cost_tracking import SessionCost, UsageData

        session_cost = SessionCost(session_id="test-session")
        usage1 = UsageData(
            message_id="msg_duplicate",
            input_tokens=100,
            output_tokens=50,
        )
        usage2 = UsageData(
            message_id="msg_duplicate",
            input_tokens=200,
            output_tokens=100,
        )

        result1 = session_cost.add_usage(usage1)
        result2 = session_cost.add_usage(usage2)

        assert result1 is True
        assert result2 is False  # Should return False for duplicate
        # Totals should only include first usage
        assert session_cost.total_input_tokens == 100
        assert session_cost.total_output_tokens == 50

    def test_set_reported_cost(self):
        """Test setting SDK-reported authoritative cost."""
        from app.core.cost_tracking import SessionCost, UsageData

        session_cost = SessionCost(session_id="test-session")

        # Add usage data
        usage1 = UsageData(
            message_id="msg_001",
            input_tokens=1000,
            output_tokens=500,
            cache_read_input_tokens=500,
        )
        usage2 = UsageData(
            message_id="msg_002",
            input_tokens=1000,
            output_tokens=500,
        )

        session_cost.add_usage(usage1)
        session_cost.add_usage(usage2)

        # Set SDK-reported cost (authoritative, model-aware)
        session_cost.set_reported_cost(0.0125)

        # Cost should be the SDK-reported value
        assert session_cost.reported_cost_usd == 0.0125
        assert session_cost.to_dict()["total_cost_usd"] == 0.0125


class TestCostStorage:
    """Test cost data persistence."""

    def test_save_session_cost(self, tmp_path):
        """Test saving session cost data to storage."""
        from app.core.cost_tracking import SessionCost, UsageData
        from app.core.storage import StorageManager

        manager = StorageManager(base_dir=tmp_path)
        # Use valid UUID v4
        session_id = "11111111-1111-4111-8111-111111111111"
        session_cost = SessionCost(session_id=session_id)

        # Add some usage
        usage = UsageData(
            message_id="msg_001",
            input_tokens=1000,
            output_tokens=500,
        )
        session_cost.add_usage(usage)

        # Convert to dict for storage (storage expects dict, not dataclass)
        cost_dict = session_cost.to_dict()

        # Save to storage
        manager.save_session_cost(session_id, cost_dict)

        # Verify file was created
        cost_file = tmp_path / "sessions" / f"{session_id}_cost.json"
        assert cost_file.exists()

    def test_get_session_cost(self, tmp_path):
        """Test retrieving session cost data from storage."""
        from app.core.cost_tracking import SessionCost, UsageData
        from app.core.storage import StorageManager

        manager = StorageManager(base_dir=tmp_path)
        # Use valid UUID v4
        session_id = "22222222-2222-4222-8222-222222222222"

        # Create and save cost data
        session_cost = SessionCost(session_id=session_id)
        usage = UsageData(
            message_id="msg_001",
            input_tokens=500,
            output_tokens=250,
        )
        session_cost.add_usage(usage)

        # Convert to dict and save
        cost_dict = session_cost.to_dict()
        manager.save_session_cost(session_id, cost_dict)

        # Retrieve it
        retrieved_cost = manager.get_session_cost(session_id)

        assert retrieved_cost is not None
        assert retrieved_cost["session_id"] == session_id
        assert retrieved_cost["total_input_tokens"] == 500
        assert retrieved_cost["total_output_tokens"] == 250

    def test_global_cost_aggregation(self, tmp_path):
        """Test aggregating costs across multiple sessions."""
        import uuid

        from app.core.cost_tracking import SessionCost, UsageData
        from app.core.storage import StorageManager

        manager = StorageManager(base_dir=tmp_path)

        # Create multiple sessions with costs
        for i in range(3):
            session_id = str(uuid.uuid4())
            session_cost = SessionCost(session_id=session_id)
            usage = UsageData(
                message_id=f"msg_{i}",
                input_tokens=1000,
                output_tokens=500,
            )
            session_cost.add_usage(usage)

            # Convert to dict for storage
            cost_dict = session_cost.to_dict()
            manager.save_session_cost(session_id, cost_dict)
            manager.update_global_cost(cost_dict)

        # Get global stats
        global_cost = manager.get_global_cost()

        assert global_cost is not None
        assert global_cost["total_input_tokens"] == 3000  # 3 sessions * 1000
        assert global_cost["total_output_tokens"] == 1500  # 3 sessions * 500
        assert global_cost["session_count"] == 3

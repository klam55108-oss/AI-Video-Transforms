"""
Tests for structured output functionality.

This module tests the Pydantic models used for structured agent responses.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError


class TestAgentResponse:
    """Test AgentResponse model."""

    def test_valid_response(self):
        """Test creating a valid AgentResponse."""
        from structured_outputs import AgentResponse

        response = AgentResponse(
            operation="transcribe",
            message="Transcription completed successfully",
            data={"transcript_id": "123", "duration": 300},
            suggestions=["Summarize the content", "Extract key points"],
        )

        assert response.operation == "transcribe"
        assert response.message == "Transcription completed successfully"
        assert response.data["transcript_id"] == "123"
        assert len(response.suggestions) == 2

    def test_operation_literals(self):
        """Test that operation field only accepts valid literals."""
        from structured_outputs import AgentResponse

        # Valid operations
        valid_operations = ["transcribe", "summarize", "save", "list", "error", "chat"]

        for op in valid_operations:
            response = AgentResponse(operation=op, message="test")
            assert response.operation == op

        # Invalid operation should raise ValidationError
        with pytest.raises(ValidationError):
            AgentResponse(operation="invalid_operation", message="test")

    def test_schema_generation(self):
        """Test that JSON schema can be generated from AgentResponse."""
        from structured_outputs import get_output_schema

        schema = get_output_schema()

        assert schema is not None
        assert "properties" in schema
        assert "operation" in schema["properties"]
        assert "message" in schema["properties"]
        # Note: 'required' field format depends on Pydantic implementation
        # Just verify the schema is valid and contains expected fields


class TestTranscriptionResult:
    """Test TranscriptionResult model."""

    def test_success_response(self):
        """Test creating a successful transcription result."""
        from structured_outputs import TranscriptionResult

        result = TranscriptionResult(
            success=True,
            transcription="This is the transcribed text",
            source="https://youtube.com/watch?v=test",
            source_type="youtube",
            segments_processed=10,
            language_detected="en",
        )

        assert result.success is True
        assert result.transcription == "This is the transcribed text"
        assert result.source_type == "youtube"
        assert result.segments_processed == 10
        assert result.language_detected == "en"
        assert result.error is None

    def test_error_response(self):
        """Test creating an error transcription result."""
        from structured_outputs import TranscriptionResult

        result = TranscriptionResult(
            success=False,
            transcription=None,
            source="invalid.mp4",
            source_type="local",
            error="File not found",
        )

        assert result.success is False
        assert result.transcription is None
        assert result.error == "File not found"

    def test_source_type_validation(self):
        """Test that source_type only accepts valid literals."""
        from structured_outputs import TranscriptionResult

        # Valid source types
        valid_types = ["youtube", "local", "upload"]

        for source_type in valid_types:
            result = TranscriptionResult(
                success=True,
                transcription="test",
                source="test.mp4",
                source_type=source_type,
            )
            assert result.source_type == source_type

        # Invalid source type should raise ValidationError
        with pytest.raises(ValidationError):
            TranscriptionResult(
                success=True,
                transcription="test",
                source="test.mp4",
                source_type="invalid_type",
            )


class TestTranscriptSummary:
    """Test TranscriptSummary model."""

    def test_valid_summary(self):
        """Test creating a valid TranscriptSummary."""
        from structured_outputs import TranscriptSummary

        summary = TranscriptSummary(
            title="Video Title",
            summary="This video discusses testing strategies",
            key_points=["Point 1", "Point 2", "Point 3"],
            topics=["Testing", "Python", "Best Practices"],
            word_count=150,
        )

        assert summary.title == "Video Title"
        assert len(summary.key_points) == 3
        assert len(summary.topics) == 3
        assert summary.word_count == 150

    def test_empty_lists_allowed(self):
        """Test that empty lists are valid for key_points and topics."""
        from structured_outputs import TranscriptSummary

        summary = TranscriptSummary(
            title="Title",
            summary="Summary text",
            key_points=[],
            topics=[],
            word_count=10,
        )

        assert summary.key_points == []
        assert summary.topics == []


class TestStructuredOutputIntegration:
    """Test integration between different structured output models."""

    def test_agent_response_with_transcription_data(self):
        """Test AgentResponse containing TranscriptionResult data."""
        from structured_outputs import AgentResponse, TranscriptionResult

        # Create a transcription result
        transcription = TranscriptionResult(
            success=True,
            transcription="Sample text",
            source="test.mp4",
            source_type="local",
        )

        # Embed it in an AgentResponse
        response = AgentResponse(
            operation="transcribe",
            message="Transcription completed",
            data=transcription.model_dump(),
        )

        assert response.data["success"] is True
        assert response.data["source_type"] == "local"

    def test_agent_response_with_summary_data(self):
        """Test AgentResponse containing TranscriptSummary data."""
        from structured_outputs import AgentResponse, TranscriptSummary

        # Create a summary
        summary = TranscriptSummary(
            title="Test Video",
            summary="This is a summary",
            key_points=["Point 1", "Point 2"],
            topics=["Testing"],
            word_count=50,
        )

        # Embed it in an AgentResponse
        response = AgentResponse(
            operation="summarize",
            message="Summary generated",
            data=summary.model_dump(),
        )

        assert response.data["title"] == "Test Video"
        assert len(response.data["key_points"]) == 2

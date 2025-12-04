"""
Storage Tests for StorageManager.

Testing Checklist Items:
- [x] Messages persist across server restarts
- [x] Session list sorted by updated_at
- [x] Transcript registration works correctly
- [x] Delete operations clean up files
"""

import json
import time
from pathlib import Path

# Valid UUID v4 test session IDs
TEST_SESSION_1 = "11111111-1111-4111-8111-111111111111"
TEST_SESSION_2 = "22222222-2222-4222-8222-222222222222"
TEST_SESSION_3 = "33333333-3333-4333-8333-333333333333"
TEST_SESSION_4 = "44444444-4444-4444-8444-444444444444"


class TestMessagePersistence:
    """Test that messages persist across server restarts."""

    def test_messages_persist_to_disk(self, temp_storage_dir: Path):
        """Test that saved messages are written to disk."""
        from app.core.storage import StorageManager

        manager = StorageManager(base_dir=temp_storage_dir)
        session_id = TEST_SESSION_1

        # Save messages
        manager.save_message(session_id, "user", "Hello agent")
        manager.save_message(session_id, "agent", "Hello user")

        # Verify file exists
        session_file = temp_storage_dir / "sessions" / f"{session_id}.json"
        assert session_file.exists(), "Session file should be created"

        # Verify content
        data = json.loads(session_file.read_text())
        assert len(data["messages"]) == 2
        assert data["messages"][0]["content"] == "Hello agent"
        assert data["messages"][1]["content"] == "Hello user"

    def test_messages_survive_new_manager_instance(self, temp_storage_dir: Path):
        """Test that messages can be read by a new StorageManager instance."""
        from app.core.storage import StorageManager

        session_id = TEST_SESSION_1

        # First manager instance saves messages
        manager1 = StorageManager(base_dir=temp_storage_dir)
        manager1.save_message(session_id, "user", "First message")
        manager1.save_message(session_id, "agent", "Second message")

        # Create new manager instance (simulating restart)
        manager2 = StorageManager(base_dir=temp_storage_dir)

        # Read session with new instance
        session = manager2.get_session(session_id)

        assert session is not None
        assert len(session["messages"]) == 2
        assert session["messages"][0]["content"] == "First message"

    def test_session_title_set_from_first_user_message(self, temp_storage_dir: Path):
        """Test that session title is set from first user message."""
        from app.core.storage import StorageManager

        manager = StorageManager(base_dir=temp_storage_dir)
        session_id = TEST_SESSION_1

        # First message from agent shouldn't set title
        manager.save_message(session_id, "agent", "Welcome!")
        session = manager.get_session(session_id)
        assert session is not None
        assert session["title"] == ""

        # First user message should set title
        manager.save_message(session_id, "user", "Please transcribe this video")
        session = manager.get_session(session_id)
        assert session is not None
        assert session["title"] == "Please transcribe this video"

    def test_long_title_is_truncated(self, temp_storage_dir: Path):
        """Test that long titles are truncated to 50 chars."""
        from app.core.storage import StorageManager

        manager = StorageManager(base_dir=temp_storage_dir)
        session_id = TEST_SESSION_1

        long_message = "A" * 100
        manager.save_message(session_id, "user", long_message)

        session = manager.get_session(session_id)
        assert session is not None
        assert len(session["title"]) == 53  # 50 chars + "..."
        assert session["title"].endswith("...")


class TestSessionListSorting:
    """Test that session list is sorted by updated_at."""

    def test_sessions_sorted_by_updated_at_descending(self, temp_storage_dir: Path):
        """Test that list_sessions returns sessions sorted newest first."""
        from app.core.storage import StorageManager

        manager = StorageManager(base_dir=temp_storage_dir)

        # Create sessions in order
        manager.save_message(TEST_SESSION_1, "user", "First session")
        time.sleep(0.01)
        manager.save_message(TEST_SESSION_2, "user", "Second session")
        time.sleep(0.01)
        manager.save_message(TEST_SESSION_3, "user", "Third session")

        sessions = manager.list_sessions()

        assert len(sessions) == 3
        # Most recently updated should be first
        assert sessions[0]["session_id"] == TEST_SESSION_3
        assert sessions[1]["session_id"] == TEST_SESSION_2
        assert sessions[2]["session_id"] == TEST_SESSION_1

    def test_update_changes_sort_order(self, temp_storage_dir: Path):
        """Test that updating a session changes its position in the list."""
        from app.core.storage import StorageManager

        manager = StorageManager(base_dir=temp_storage_dir)

        # Create sessions
        manager.save_message(TEST_SESSION_1, "user", "Old session")
        time.sleep(0.01)
        manager.save_message(TEST_SESSION_2, "user", "New session")

        # Initially, TEST_SESSION_2 should be first (most recent)
        sessions = manager.list_sessions()
        assert sessions[0]["session_id"] == TEST_SESSION_2

        # Update old session
        time.sleep(0.01)
        manager.save_message(TEST_SESSION_1, "user", "Updated message")

        # Now TEST_SESSION_1 should be first
        sessions = manager.list_sessions()
        assert sessions[0]["session_id"] == TEST_SESSION_1

    def test_list_sessions_respects_limit(self, temp_storage_dir: Path):
        """Test that list_sessions respects the limit parameter."""
        import uuid as uuid_module

        from app.core.storage import StorageManager

        manager = StorageManager(base_dir=temp_storage_dir)

        # Create many sessions using valid UUIDs
        for i in range(10):
            session_id = str(uuid_module.uuid4())
            manager.save_message(session_id, "user", f"Session {i}")

        # Request only 3
        sessions = manager.list_sessions(limit=3)
        assert len(sessions) == 3


class TestTranscriptRegistration:
    """Test that transcript registration works correctly."""

    def test_register_transcript_creates_entry(
        self, temp_storage_dir: Path, sample_transcript_content: str
    ):
        """Test that register_transcript creates a metadata entry."""
        from app.core.storage import StorageManager

        manager = StorageManager(base_dir=temp_storage_dir)

        # Create a transcript file
        transcript_file = temp_storage_dir / "test_transcript.txt"
        transcript_file.write_text(sample_transcript_content)

        # Register it (use valid UUID format for session_id)
        entry = manager.register_transcript(
            file_path=str(transcript_file),
            original_source="https://youtube.com/watch?v=test",
            source_type="youtube",
            session_id="12345678-1234-4123-8123-123456789abc",
        )

        assert entry["id"] is not None
        assert entry["filename"] == "test_transcript.txt"
        assert entry["source_type"] == "youtube"
        assert entry["file_size"] > 0

    def test_list_transcripts_returns_all(
        self, temp_storage_dir: Path, sample_transcript_content: str
    ):
        """Test that list_transcripts returns all registered transcripts."""
        from app.core.storage import StorageManager

        manager = StorageManager(base_dir=temp_storage_dir)

        # Create and register multiple transcripts
        for i in range(3):
            transcript_file = temp_storage_dir / f"transcript_{i}.txt"
            transcript_file.write_text(sample_transcript_content)
            manager.register_transcript(
                file_path=str(transcript_file),
                original_source=f"source_{i}",
                source_type="local",
            )

        transcripts = manager.list_transcripts()
        assert len(transcripts) == 3

    def test_get_transcript_returns_correct_entry(
        self, temp_storage_dir: Path, sample_transcript_content: str
    ):
        """Test that get_transcript returns the correct metadata."""
        from app.core.storage import StorageManager

        manager = StorageManager(base_dir=temp_storage_dir)

        transcript_file = temp_storage_dir / "specific_transcript.txt"
        transcript_file.write_text(sample_transcript_content)

        entry = manager.register_transcript(
            file_path=str(transcript_file),
            original_source="test_source",
            source_type="upload",
        )

        retrieved = manager.get_transcript(entry["id"])

        assert retrieved is not None
        assert retrieved["id"] == entry["id"]
        assert retrieved["original_source"] == "test_source"

    def test_get_nonexistent_transcript_returns_none(self, temp_storage_dir: Path):
        """Test that get_transcript returns None for unknown ID."""
        from app.core.storage import StorageManager

        manager = StorageManager(base_dir=temp_storage_dir)
        result = manager.get_transcript("nonexistent-id")
        assert result is None


class TestDeleteOperations:
    """Test that delete operations clean up files."""

    def test_delete_session_removes_file(self, temp_storage_dir: Path):
        """Test that delete_session removes the session file."""
        from app.core.storage import StorageManager

        manager = StorageManager(base_dir=temp_storage_dir)
        session_id = TEST_SESSION_1

        # Create session
        manager.save_message(session_id, "user", "Test message")
        session_file = temp_storage_dir / "sessions" / f"{session_id}.json"
        assert session_file.exists()

        # Delete session
        success = manager.delete_session(session_id)

        assert success is True
        assert not session_file.exists()

    def test_delete_nonexistent_session_returns_false(self, temp_storage_dir: Path):
        """Test that deleting nonexistent session returns False."""
        from app.core.storage import StorageManager

        manager = StorageManager(base_dir=temp_storage_dir)
        success = manager.delete_session("nonexistent-session")
        assert success is False

    def test_delete_transcript_removes_metadata_and_file(
        self, temp_storage_dir: Path, sample_transcript_content: str
    ):
        """Test that delete_transcript removes both metadata and file."""
        from app.core.storage import StorageManager

        manager = StorageManager(base_dir=temp_storage_dir)

        # Create and register transcript
        transcript_file = temp_storage_dir / "to_delete.txt"
        transcript_file.write_text(sample_transcript_content)

        entry = manager.register_transcript(
            file_path=str(transcript_file),
            original_source="test",
            source_type="local",
        )

        # Verify file exists
        assert transcript_file.exists()

        # Delete transcript
        success = manager.delete_transcript(entry["id"])

        assert success is True
        assert not transcript_file.exists()
        assert manager.get_transcript(entry["id"]) is None

    def test_delete_transcript_handles_missing_file(
        self, temp_storage_dir: Path, sample_transcript_content: str
    ):
        """Test that delete_transcript works even if file is already gone."""
        from app.core.storage import StorageManager

        manager = StorageManager(base_dir=temp_storage_dir)

        # Create and register transcript
        transcript_file = temp_storage_dir / "will_be_deleted.txt"
        transcript_file.write_text(sample_transcript_content)

        entry = manager.register_transcript(
            file_path=str(transcript_file),
            original_source="test",
            source_type="local",
        )

        # Manually delete the file
        transcript_file.unlink()

        # delete_transcript should still succeed (removing metadata)
        success = manager.delete_transcript(entry["id"])

        assert success is True
        assert manager.get_transcript(entry["id"]) is None

    def test_delete_nonexistent_transcript_returns_false(self, temp_storage_dir: Path):
        """Test that deleting nonexistent transcript returns False."""
        from app.core.storage import StorageManager

        manager = StorageManager(base_dir=temp_storage_dir)
        success = manager.delete_transcript("nonexistent-id")
        assert success is False


class TestStorageManagerInitialization:
    """Test StorageManager initialization and directory creation."""

    def test_creates_required_directories(self, temp_storage_dir: Path):
        """Test that StorageManager creates required directories."""
        from app.core.storage import StorageManager

        # Remove the temp dir contents to test creation
        import shutil

        shutil.rmtree(temp_storage_dir)

        StorageManager(base_dir=temp_storage_dir)  # Side effect: creates directories

        assert temp_storage_dir.exists()
        assert (temp_storage_dir / "sessions").exists()
        assert (temp_storage_dir / "transcripts").exists()

    def test_handles_existing_directories(self, temp_storage_dir: Path):
        """Test that StorageManager works with existing directories."""
        from app.core.storage import StorageManager

        # Create directories first
        (temp_storage_dir / "sessions").mkdir(parents=True, exist_ok=True)
        (temp_storage_dir / "transcripts").mkdir(parents=True, exist_ok=True)

        # Should not raise
        manager = StorageManager(base_dir=temp_storage_dir)

        assert manager.sessions_dir.exists()
        assert manager.transcripts_dir.exists()

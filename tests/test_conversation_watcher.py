"""Tests for conversation watcher module."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from mcp_claude_memories.conversation_watcher import (
    ConversationFileHandler,
    ConversationWatcher,
)


@pytest.fixture
def mock_memory_service():
    """Mock memory service for testing."""
    service = Mock()
    service.store_conversation = AsyncMock(return_value="memory_123")
    return service


@pytest.fixture
def temp_claude_config():
    """Create temporary Claude config directory structure."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_dir = Path(temp_dir)
        projects_dir = config_dir / "projects"
        projects_dir.mkdir()

        # Create test project directories
        project1 = projects_dir / "project1"
        project2 = projects_dir / "project2"
        project1.mkdir()
        project2.mkdir()

        yield config_dir


@pytest.fixture
def conversation_watcher(mock_memory_service, temp_claude_config):
    """Conversation watcher instance for testing."""
    return ConversationWatcher(
        memory_service=mock_memory_service,
        claude_config_dir=temp_claude_config,
        watch_patterns=["conversation*.jsonl"],
        default_user_id="test_user",
    )


def create_conversation_file(directory: Path, filename: str, content: list[str]):
    """Create a conversation JSONL file with given content."""
    file_path = directory / filename
    with open(file_path, "w") as f:
        for line in content:
            f.write(line + "\n")
    return file_path


@pytest.mark.asyncio
async def test_process_existing_files(
    conversation_watcher, temp_claude_config, mock_memory_service
):
    """Test processing existing conversation files on startup."""
    # Create test conversation files
    project1_dir = temp_claude_config / "projects" / "project1"
    project2_dir = temp_claude_config / "projects" / "project2"

    conv1_content = [
        '{"role": "user", "content": "Hello", "timestamp": "2025-07-02T10:00:00Z"}',
        '{"role": "assistant", "content": "Hi there!", "timestamp": "2025-07-02T10:00:01Z"}',
    ]

    conv2_content = [
        '{"role": "user", "content": "How are you?", "timestamp": "2025-07-02T10:01:00Z"}'
    ]

    create_conversation_file(project1_dir, "conversation_abc.jsonl", conv1_content)
    create_conversation_file(project2_dir, "conversation_def.jsonl", conv2_content)

    # Manually populate watched directories for this test
    conversation_watcher._watched_dirs.add(project1_dir)
    conversation_watcher._watched_dirs.add(project2_dir)

    # Process existing files
    await conversation_watcher._process_existing_files()

    # Verify store_conversation was called for both files
    assert mock_memory_service.store_conversation.call_count == 2

    # Collect all the calls
    calls = mock_memory_service.store_conversation.call_args_list

    # Extract project names and message counts from calls
    call_data = []
    for call in calls:
        call_data.append({
            "user_id": call[1]["user_id"],
            "project_name": call[1]["project_name"],
            "message_count": len(call[1]["messages"]),
        })

    # Check that both projects were processed
    project_names = {call["project_name"] for call in call_data}
    assert project_names == {"project1", "project2"}

    # Check that all calls have correct user_id
    assert all(call["user_id"] == "test_user" for call in call_data)

    # Check message counts (project1 has 2 messages, project2 has 1)
    message_counts = [call["message_count"] for call in call_data]
    assert sorted(message_counts) == [1, 2]

    # Check that messages are in the correct format for memory service
    for call in calls:
        messages = call[1]["messages"]
        for msg in messages:
            assert "role" in msg
            assert "content" in msg
            assert msg["role"] in ["human", "assistant"]


@pytest.mark.asyncio
async def test_process_file_changes_new_file(
    conversation_watcher, temp_claude_config, mock_memory_service
):
    """Test processing a completely new file."""
    project_dir = temp_claude_config / "projects" / "project1"
    file_path = create_conversation_file(
        project_dir,
        "conversation_new.jsonl",
        [
            '{"role": "user", "content": "New conversation", "timestamp": "2025-07-02T12:00:00Z"}',
            '{"role": "assistant", "content": "Hello!", "timestamp": "2025-07-02T12:00:01Z"}',
        ],
    )

    await conversation_watcher._process_file_changes(file_path, is_startup=True)

    # Verify memory storage
    mock_memory_service.store_conversation.assert_called_once()
    call_args = mock_memory_service.store_conversation.call_args[1]

    assert call_args["user_id"] == "test_user"
    assert call_args["project_name"] == "project1"
    assert len(call_args["messages"]) == 2
    assert call_args["messages"][0]["content"] == "New conversation"


@pytest.mark.asyncio
async def test_process_file_changes_incremental(
    conversation_watcher, temp_claude_config, mock_memory_service
):
    """Test processing incremental changes to existing file."""
    project_dir = temp_claude_config / "projects" / "project1"
    file_path = create_conversation_file(
        project_dir,
        "conversation_inc.jsonl",
        [
            '{"role": "user", "content": "First message", "timestamp": "2025-07-02T12:00:00Z"}',
            '{"role": "assistant", "content": "First response", "timestamp": "2025-07-02T12:00:01Z"}',
        ],
    )

    # Process initial file
    await conversation_watcher._process_file_changes(file_path, is_startup=True)

    # Add more content to file
    with open(file_path, "a") as f:
        f.write(
            '{"role": "user", "content": "Second message", "timestamp": "2025-07-02T12:01:00Z"}\n'
        )
        f.write(
            '{"role": "assistant", "content": "Second response", "timestamp": "2025-07-02T12:01:01Z"}\n'
        )

    # Process incremental changes
    await conversation_watcher._process_file_changes(file_path)

    # Should have been called twice
    assert mock_memory_service.store_conversation.call_count == 2

    # Second call should only have the new messages
    second_call = mock_memory_service.store_conversation.call_args_list[1]
    assert len(second_call[1]["messages"]) == 2
    assert second_call[1]["messages"][0]["content"] == "Second message"


@pytest.mark.asyncio
async def test_process_file_changes_no_new_content(
    conversation_watcher, temp_claude_config, mock_memory_service
):
    """Test processing file with no new content."""
    project_dir = temp_claude_config / "projects" / "project1"
    file_path = create_conversation_file(
        project_dir,
        "conversation_same.jsonl",
        ['{"role": "user", "content": "Message", "timestamp": "2025-07-02T12:00:00Z"}'],
    )

    # Process file initially
    await conversation_watcher._process_file_changes(file_path, is_startup=True)

    # Process again without changes
    await conversation_watcher._process_file_changes(file_path)

    # Should only be called once
    mock_memory_service.store_conversation.assert_called_once()


@pytest.mark.asyncio
async def test_process_file_changes_no_messages(
    conversation_watcher, temp_claude_config, mock_memory_service
):
    """Test processing file with no extractable messages."""
    project_dir = temp_claude_config / "projects" / "project1"
    file_path = create_conversation_file(
        project_dir,
        "conversation_empty.jsonl",
        [
            '{"role": "system", "content": "System message"}',  # Should be ignored
            '{"type": "other", "data": "some data"}',  # Should be ignored
            "invalid json",  # Should be ignored
        ],
    )

    await conversation_watcher._process_file_changes(file_path, is_startup=True)

    # Should not call store_conversation
    mock_memory_service.store_conversation.assert_not_called()


def test_get_watch_directories(conversation_watcher, temp_claude_config):
    """Test getting list of directories to watch."""
    watch_dirs = conversation_watcher._get_watch_directories()

    assert len(watch_dirs) == 2
    assert temp_claude_config / "projects" / "project1" in watch_dirs
    assert temp_claude_config / "projects" / "project2" in watch_dirs


def test_get_watch_directories_no_projects(conversation_watcher):
    """Test getting directories when projects dir doesn't exist."""
    # Use non-existent config dir
    conversation_watcher.claude_config_dir = Path("/nonexistent")

    watch_dirs = conversation_watcher._get_watch_directories()

    assert watch_dirs == []


def test_get_processing_status(conversation_watcher):
    """Test getting processing status."""
    # Set some test state
    conversation_watcher._watched_dirs = {Path("/test/dir1"), Path("/test/dir2")}
    conversation_watcher._file_positions = {
        "/test/file1.jsonl": 10,
        "/test/file2.jsonl": 5,
    }

    status = conversation_watcher.get_processing_status()

    assert len(status["watched_directories"]) == 2
    assert "/test/dir1" in status["watched_directories"]
    assert "/test/dir2" in status["watched_directories"]
    assert status["file_positions"] == {"/test/file1.jsonl": 10, "/test/file2.jsonl": 5}
    assert status["watch_patterns"] == ["conversation*.jsonl"]
    assert status["is_watching"] is False  # Observer not started


def test_file_handler_matches_patterns():
    """Test file pattern matching in handler."""
    watcher = Mock()
    watcher.watch_patterns = ["conversation*.jsonl", "chat*.jsonl"]

    handler = ConversationFileHandler(watcher)

    # Should match
    assert handler._matches_patterns(Path("conversation_abc.jsonl")) is True
    assert handler._matches_patterns(Path("chat_def.jsonl")) is True

    # Should not match
    assert handler._matches_patterns(Path("other_file.jsonl")) is False
    assert handler._matches_patterns(Path("conversation.txt")) is False


@pytest.mark.asyncio
async def test_file_handler_on_modified():
    """Test file modification event handling."""
    watcher = Mock()
    watcher.watch_patterns = ["conversation*.jsonl"]
    watcher._process_file_changes = AsyncMock()

    handler = ConversationFileHandler(watcher)

    # Create mock event
    event = Mock()
    event.is_directory = False
    event.src_path = "/test/conversation_abc.jsonl"

    # Handle event
    handler.on_modified(event)

    # Wait a bit for debouncing
    await asyncio.sleep(0.1)

    # Should have scheduled processing (we can't easily test the async task creation)
    # This is more of a smoke test to ensure no exceptions


def test_file_handler_on_modified_directory():
    """Test that directory events are ignored."""
    watcher = Mock()
    handler = ConversationFileHandler(watcher)

    # Create directory event
    event = Mock()
    event.is_directory = True
    event.src_path = "/test/directory"

    # Should not process directory events
    handler.on_modified(event)

    # No processing should occur (no easy way to verify, but should not crash)


def test_file_handler_on_modified_non_matching():
    """Test that non-matching files are ignored."""
    watcher = Mock()
    watcher.watch_patterns = ["conversation*.jsonl"]

    handler = ConversationFileHandler(watcher)

    # Create event for non-matching file
    event = Mock()
    event.is_directory = False
    event.src_path = "/test/other_file.txt"

    # Should not process non-matching files
    handler.on_modified(event)

    # No processing should occur


@pytest.mark.asyncio
async def test_process_existing_files_with_type_field(
    conversation_watcher, temp_claude_config, mock_memory_service
):
    """Test processing existing conversation files using Claude's actual 'type' field format."""
    # Create test conversation files using correct Claude Code format
    project1_dir = temp_claude_config / "projects" / "project1"
    project2_dir = temp_claude_config / "projects" / "project2"

    conv1_content = [
        '{"type": "user", "content": "Hello", "timestamp": "2025-07-02T10:00:00Z"}',
        '{"type": "assistant", "content": "Hi there!", "timestamp": "2025-07-02T10:00:01Z"}',
    ]

    conv2_content = [
        '{"type": "user", "content": "How are you?", "timestamp": "2025-07-02T10:01:00Z"}'
    ]

    create_conversation_file(project1_dir, "conversation_abc.jsonl", conv1_content)
    create_conversation_file(project2_dir, "conversation_def.jsonl", conv2_content)

    # Manually populate watched directories for this test
    conversation_watcher._watched_dirs.add(project1_dir)
    conversation_watcher._watched_dirs.add(project2_dir)

    # Process existing files
    await conversation_watcher._process_existing_files()

    # Verify store_conversation was called for both files
    assert mock_memory_service.store_conversation.call_count == 2

    # Collect all the calls
    calls = mock_memory_service.store_conversation.call_args_list

    # Extract project names and message counts from calls
    call_data = []
    for call in calls:
        call_data.append({
            "user_id": call[1]["user_id"],
            "project_name": call[1]["project_name"],
            "message_count": len(call[1]["messages"]),
        })

    # Check that both projects were processed
    project_names = {call["project_name"] for call in call_data}
    assert project_names == {"project1", "project2"}

    # Check that all calls have correct user_id
    assert all(call["user_id"] == "test_user" for call in call_data)

    # Check message counts (project1 has 2 messages, project2 has 1)
    message_counts = [call["message_count"] for call in call_data]
    assert sorted(message_counts) == [1, 2]

    # Check that messages are in the correct format for memory service
    for call in calls:
        messages = call[1]["messages"]
        for msg in messages:
            assert "role" in msg
            assert "content" in msg
            assert msg["role"] in ["human", "assistant"]


@pytest.mark.asyncio
async def test_process_file_changes_with_type_field(
    conversation_watcher, temp_claude_config, mock_memory_service
):
    """Test processing file changes using Claude's actual 'type' field format."""
    project_dir = temp_claude_config / "projects" / "project1"
    file_path = create_conversation_file(
        project_dir,
        "conversation_type.jsonl",
        [
            '{"type": "user", "content": "Type field test", "timestamp": "2025-07-02T12:00:00Z"}',
            '{"type": "assistant", "content": "Works correctly!", "timestamp": "2025-07-02T12:00:01Z"}',
        ],
    )

    await conversation_watcher._process_file_changes(file_path, is_startup=True)

    # Verify memory storage
    mock_memory_service.store_conversation.assert_called_once()
    call_args = mock_memory_service.store_conversation.call_args[1]

    assert call_args["user_id"] == "test_user"
    assert call_args["project_name"] == "project1"
    assert len(call_args["messages"]) == 2
    assert call_args["messages"][0]["content"] == "Type field test"
    assert call_args["messages"][0]["role"] == "human"  # user mapped to human
    assert call_args["messages"][1]["content"] == "Works correctly!"
    assert call_args["messages"][1]["role"] == "assistant"

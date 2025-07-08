"""Tests for conversation parser module."""

import tempfile
from pathlib import Path

import pytest

from mcp_claude_memories.conversation_parser import ConversationParser


@pytest.fixture
def parser():
    """Conversation parser instance."""
    return ConversationParser()


@pytest.fixture
def sample_jsonl_content():
    """Sample JSONL content for testing."""
    return [
        '{"role": "user", "content": "Hello", "timestamp": "2025-07-02T10:00:00Z"}',
        '{"role": "assistant", "content": "Hi there!", "timestamp": "2025-07-02T10:00:01Z"}',
        '{"role": "user", "content": "How are you?", "timestamp": "2025-07-02T10:00:02Z"}',
        "",  # Empty line should be skipped
        '{"role": "system", "content": "System message"}',  # System messages should be skipped
        "invalid json line",  # Invalid JSON should be skipped
        '{"role": "assistant", "content": "I\'m doing well!", "timestamp": "2025-07-02T10:00:03Z"}',
    ]


def create_temp_jsonl_file(content_lines):
    """Create temporary JSONL file with given content."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False
    ) as temp_file:
        for line in content_lines:
            temp_file.write(line + "\n")
        return Path(temp_file.name)


def test_parse_jsonl_file_success(parser, sample_jsonl_content):
    """Test successful JSONL file parsing."""
    temp_file = create_temp_jsonl_file(sample_jsonl_content)

    try:
        result = parser.parse_jsonl_file(temp_file)

        # Should parse 5 valid JSON lines (skipping empty and invalid)
        assert len(result) == 5

        # Check first valid entry
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "Hello"
        assert result[0]["_line_number"] == 0

        # Check that line numbers are preserved
        assert result[1]["_line_number"] == 1
        assert result[2]["_line_number"] == 2

    finally:
        temp_file.unlink()


def test_parse_jsonl_file_with_start_line(parser, sample_jsonl_content):
    """Test parsing JSONL file from specific start line."""
    temp_file = create_temp_jsonl_file(sample_jsonl_content)

    try:
        result = parser.parse_jsonl_file(temp_file, start_line=2)

        # Should parse from line 2 onwards
        assert len(result) == 3
        assert result[0]["_line_number"] == 2
        assert result[0]["content"] == "How are you?"

    finally:
        temp_file.unlink()


def test_parse_jsonl_file_not_found(parser):
    """Test parsing non-existent file."""
    result = parser.parse_jsonl_file(Path("/nonexistent/file.jsonl"))

    assert result == []


def test_extract_messages(parser):
    """Test extracting messages from parsed JSONL data."""
    jsonl_data = [
        {
            "role": "user",
            "content": "Hello",
            "timestamp": "2025-07-02T10:00:00Z",
            "_line_number": 0,
        },
        {
            "role": "assistant",
            "content": "Hi there!",
            "timestamp": "2025-07-02T10:00:01Z",
            "_line_number": 1,
        },
        {"role": "system", "content": "System message", "_line_number": 2},
        {
            "role": "user",
            "content": "",  # Empty content should be skipped
            "_line_number": 3,
        },
    ]

    result = parser.extract_messages(jsonl_data)

    # Should extract only user and assistant messages with content
    assert len(result) == 2

    assert result[0]["role"] == "user"
    assert result[0]["content"] == "Hello"
    assert result[0]["line_number"] == 0

    assert result[1]["role"] == "assistant"
    assert result[1]["content"] == "Hi there!"
    assert result[1]["line_number"] == 1


def test_extract_messages_with_list_content(parser):
    """Test extracting messages with content as list (text blocks)."""
    jsonl_data = [
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "First part"},
                {"type": "text", "text": "Second part"},
                {
                    "type": "image",
                    "url": "http://example.com/image.png",
                },  # Should be ignored
            ],
            "_line_number": 0,
        }
    ]

    result = parser.extract_messages(jsonl_data)

    assert len(result) == 1
    assert result[0]["content"] == "First part\nSecond part"


def test_extract_metadata(parser):
    """Test extracting metadata from file path and JSONL data."""
    # Create a path that looks like Claude's structure
    file_path = Path(
        "/home/user/.config/claude/projects/my-project/conversation_abc123.jsonl"
    )

    jsonl_data = [
        {"timestamp": "2025-07-02T10:00:00Z", "_line_number": 0},
        {"timestamp": "2025-07-02T10:00:05Z", "_line_number": 4},
    ]

    result = parser.extract_metadata(file_path, jsonl_data)

    assert result["file_name"] == "conversation_abc123.jsonl"
    assert result["project_name"] == "my-project"
    assert result["conversation_id"] == "abc123"
    assert result["total_lines"] == 2
    assert result["first_timestamp"] == "2025-07-02T10:00:00Z"
    assert result["last_timestamp"] == "2025-07-02T10:00:05Z"
    assert result["first_line"] == 0
    assert result["last_line"] == 4


def test_extract_project_name(parser):
    """Test extracting project name from various path formats."""
    # Standard Claude path
    path1 = Path("/home/user/.config/claude/projects/my-project/conversation.jsonl")
    assert parser._extract_project_name(path1) == "my-project"

    # Different structure
    path2 = Path("/some/other/projects/another-project/file.jsonl")
    assert parser._extract_project_name(path2) == "another-project"

    # No projects directory
    path3 = Path("/some/random/path/file.jsonl")
    assert parser._extract_project_name(path3) == "unknown"


def test_extract_conversation_id(parser):
    """Test extracting conversation ID from filenames."""
    # Standard format
    path1 = Path("conversation_abc123.jsonl")
    assert parser._extract_conversation_id(path1) == "abc123"

    # Different format
    path2 = Path("chat_xyz789.jsonl")
    assert parser._extract_conversation_id(path2) == "xyz789"

    # No underscore
    path3 = Path("conversation.jsonl")
    assert parser._extract_conversation_id(path3) == "conversation"


def test_is_message_entry(parser):
    """Test message entry validation."""
    # Valid user message
    entry1 = {"role": "user", "content": "Hello"}
    assert parser._is_message_entry(entry1) is True

    # Valid assistant message
    entry2 = {"role": "assistant", "content": "Hi there!"}
    assert parser._is_message_entry(entry2) is True

    # System message (should be excluded)
    entry3 = {"role": "system", "content": "System message"}
    assert parser._is_message_entry(entry3) is False

    # Missing role
    entry4 = {"content": "Hello"}
    assert parser._is_message_entry(entry4) is False

    # Missing content
    entry5 = {"role": "user"}
    assert parser._is_message_entry(entry5) is False

    # Empty content
    entry6 = {"role": "user", "content": ""}
    assert parser._is_message_entry(entry6) is False


def test_extract_content_string(parser):
    """Test extracting content when it's a string."""
    entry = {"content": "Simple text content"}

    result = parser._extract_content(entry)

    assert result == "Simple text content"


def test_extract_content_list(parser):
    """Test extracting content when it's a list of objects."""
    entry = {
        "content": [
            {"type": "text", "text": "First block"},
            {"type": "text", "text": "Second block"},
            {"type": "tool_call", "name": "search"},  # Should be ignored
            "Raw string",  # Should be included
        ]
    }

    result = parser._extract_content(entry)

    assert result == "First block\nSecond block\nRaw string"


def test_extract_content_none(parser):
    """Test extracting content when it's not extractable."""
    entry1 = {"content": None}
    assert parser._extract_content(entry1) is None

    entry2 = {"content": []}
    assert parser._extract_content(entry2) is None

    entry3 = {"content": 123}
    assert parser._extract_content(entry3) is None


def test_get_file_line_count(parser, sample_jsonl_content):
    """Test getting file line count."""
    temp_file = create_temp_jsonl_file(sample_jsonl_content)

    try:
        result = parser.get_file_line_count(temp_file)

        assert result == len(sample_jsonl_content)

    finally:
        temp_file.unlink()


def test_get_file_line_count_not_found(parser):
    """Test getting line count for non-existent file."""
    result = parser.get_file_line_count(Path("/nonexistent/file.jsonl"))

    assert result == 0


def test_extract_conversation_messages(parser):
    """Test extracting conversation messages in memory service format."""
    jsonl_data = [
        {
            "role": "user",
            "content": "Hello world",
            "timestamp": "2025-07-02T10:00:00Z",
            "_line_number": 0,
        },
        {
            "role": "assistant",
            "content": "Hi there!",
            "timestamp": "2025-07-02T10:00:01Z",
            "_line_number": 1,
        },
        {"role": "system", "content": "System message", "_line_number": 2},
        {
            "role": "user",
            "content": "",  # Empty content should be skipped
            "_line_number": 3,
        },
    ]

    result = parser.extract_conversation_messages(jsonl_data)

    # Should extract only user and assistant messages with content
    assert len(result) == 2

    # Check format for memory service
    assert result[0]["role"] == "human"  # user mapped to human
    assert result[0]["content"] == "Hello world"

    assert result[1]["role"] == "assistant"  # assistant stays assistant
    assert result[1]["content"] == "Hi there!"

    # Should not include timestamps or line numbers in memory format
    assert "timestamp" not in result[0]
    assert "line_number" not in result[0]


def test_extract_conversation_messages_empty_input(parser):
    """Test extracting conversation messages with empty input."""
    result = parser.extract_conversation_messages([])
    assert result == []


def test_extract_conversation_messages_no_valid_messages(parser):
    """Test extracting conversation messages with no valid messages."""
    jsonl_data = [
        {"role": "system", "content": "System message"},
        {"role": "user", "content": ""},  # Empty content
        {"invalid": "entry"},  # Invalid entry
    ]

    result = parser.extract_conversation_messages(jsonl_data)
    assert result == []

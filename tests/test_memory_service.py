"""Tests for memory service module."""

from unittest.mock import Mock, patch

import pytest

from mcp_claude_memories.memory_service import MemoryService


@pytest.fixture
def mock_mem0_client():
    """Mock Mem0 client for testing."""
    with patch("mcp_claude_memories.memory_service.MemoryClient") as mock_client_class:
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        yield mock_client


@pytest.fixture
def memory_service(mock_mem0_client):
    """Memory service instance with mocked client."""
    return MemoryService(api_key="test_key")


@pytest.mark.asyncio
async def test_store_conversation_success(memory_service, mock_mem0_client):
    """Test successful conversation storage."""
    # Mock successful response
    mock_mem0_client.add.return_value = {"id": "memory_123"}

    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
    ]

    result = await memory_service.store_conversation(
        user_id="test_user",
        project_name="test_project",
        messages=messages,
        metadata={"extra": "data"},
    )

    assert result == "memory_123"

    # Verify client was called with correct parameters
    mock_mem0_client.add.assert_called_once()
    call_args = mock_mem0_client.add.call_args[1]

    assert call_args["user_id"] == "test_user"
    assert len(call_args["messages"]) == 2
    assert call_args["messages"][0]["role"] == "user"
    assert call_args["messages"][0]["content"] == "Hello"
    assert call_args["metadata"]["project_name"] == "test_project"
    assert call_args["metadata"]["extra"] == "data"


@pytest.mark.asyncio
async def test_store_conversation_failure(memory_service, mock_mem0_client):
    """Test conversation storage failure."""
    # Mock API failure
    mock_mem0_client.add.side_effect = Exception("API Error")

    messages = [{"role": "user", "content": "Hello"}]

    with pytest.raises(Exception, match="API Error"):
        await memory_service.store_conversation(
            user_id="test_user", project_name="test_project", messages=messages
        )


@pytest.mark.asyncio
async def test_search_memories_success(memory_service, mock_mem0_client):
    """Test successful memory search."""
    # Mock search results
    mock_mem0_client.search.return_value = {
        "memories": [
            {"id": "mem1", "memory": "Test memory 1"},
            {"id": "mem2", "memory": "Test memory 2"},
        ]
    }

    result = await memory_service.search_memories(
        query="test query", user_id="test_user", limit=5
    )

    assert len(result) == 2
    assert result[0]["id"] == "mem1"
    assert result[1]["id"] == "mem2"

    mock_mem0_client.search.assert_called_once_with(
        query="test query", user_id="test_user", limit=5
    )


@pytest.mark.asyncio
async def test_search_memories_no_results(memory_service, mock_mem0_client):
    """Test memory search with no results."""
    mock_mem0_client.search.return_value = {"memories": []}

    result = await memory_service.search_memories(query="nonexistent")

    assert result == []


@pytest.mark.asyncio
async def test_get_memories_success(memory_service, mock_mem0_client):
    """Test successful memory retrieval."""
    mock_mem0_client.get_all.return_value = {
        "memories": [
            {"id": "mem1", "memory": "Recent memory 1"},
            {"id": "mem2", "memory": "Recent memory 2"},
        ]
    }

    result = await memory_service.get_memories(user_id="test_user", limit=10)

    assert len(result) == 2
    mock_mem0_client.get_all.assert_called_once_with(user_id="test_user", limit=10)


@pytest.mark.asyncio
async def test_delete_memory_success(memory_service, mock_mem0_client):
    """Test successful memory deletion."""
    mock_mem0_client.delete.return_value = {"status": "deleted"}

    result = await memory_service.delete_memory("memory_123")

    assert result is True
    mock_mem0_client.delete.assert_called_once_with(memory_id="memory_123")


@pytest.mark.asyncio
async def test_delete_memory_failure(memory_service, mock_mem0_client):
    """Test memory deletion failure."""
    mock_mem0_client.delete.return_value = None

    result = await memory_service.delete_memory("memory_123")

    assert result is False


def test_format_memory_for_display(memory_service):
    """Test memory formatting for display."""
    memory = {
        "id": "mem_123",
        "memory": "This is a test memory",
        "metadata": {
            "project_name": "Test Project",
            "timestamp": "2025-07-02T10:30:00Z",
        },
    }

    result = memory_service.format_memory_for_display(memory)

    assert "mem_123" in result
    assert "Test Project" in result
    assert "This is a test memory" in result
    assert "2025-07-02" in result


def test_format_memories_list(memory_service):
    """Test formatting a list of memories."""
    memories = [
        {
            "id": "mem1",
            "memory": "Memory 1",
            "metadata": {
                "project_name": "Project 1",
                "timestamp": "2025-07-02T10:30:00Z",
            },
        },
        {
            "id": "mem2",
            "memory": "Memory 2",
            "metadata": {
                "project_name": "Project 2",
                "timestamp": "2025-07-02T11:30:00Z",
            },
        },
    ]

    result = memory_service.format_memories_list(memories)

    assert "1." in result
    assert "2." in result
    assert "mem1" in result
    assert "mem2" in result
    assert "Memory 1" in result
    assert "Memory 2" in result


def test_format_memories_list_empty(memory_service):
    """Test formatting empty memories list."""
    result = memory_service.format_memories_list([])

    assert result == "No memories found."

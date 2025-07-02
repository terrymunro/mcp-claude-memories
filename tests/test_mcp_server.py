"""Tests for MCP server tools."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from mcp_claude_memories import mcp_server


@pytest.fixture
def mock_memory_service():
    """Mock memory service for testing."""
    service = Mock()
    service.search_memories = AsyncMock()
    service.get_memories = AsyncMock()
    service.store_conversation = AsyncMock()
    service.delete_memory = AsyncMock()
    service.format_memories_list = Mock()
    return service


@pytest.fixture
def mock_reflection_agent():
    """Mock reflection agent for testing."""
    agent = Mock()
    agent.analyze_patterns = AsyncMock()
    agent.generate_insights = Mock()
    agent.suggest_actions = AsyncMock()
    return agent


@pytest.fixture
def setup_server_globals(mock_memory_service, mock_reflection_agent):
    """Setup global variables in mcp_server module."""
    mcp_server.memory_service = mock_memory_service
    mcp_server.reflection_agent = mock_reflection_agent
    yield
    # Cleanup
    mcp_server.memory_service = None
    mcp_server.reflection_agent = None


@pytest.mark.asyncio
async def test_search_memories_success(setup_server_globals, mock_memory_service):
    """Test successful memory search."""
    # Setup mocks
    mock_memories = [
        {"id": "mem1", "memory": "Test memory 1"},
        {"id": "mem2", "memory": "Test memory 2"},
    ]
    mock_memory_service.search_memories.return_value = mock_memories
    mock_memory_service.format_memories_list.return_value = "Formatted memories"

    # Call tool
    result = await mcp_server.search_memories(
        "test query", limit=5, user_id="test_user"
    )

    # Verify
    assert result == "Formatted memories"
    mock_memory_service.search_memories.assert_called_once_with(
        "test query", "test_user", 5
    )
    mock_memory_service.format_memories_list.assert_called_once_with(mock_memories)


@pytest.mark.asyncio
async def test_search_memories_no_results(setup_server_globals, mock_memory_service):
    """Test memory search with no results."""
    mock_memory_service.search_memories.return_value = []

    result = await mcp_server.search_memories("nonexistent query")

    assert "No memories found" in result
    assert "nonexistent query" in result


@pytest.mark.asyncio
async def test_search_memories_error(setup_server_globals, mock_memory_service):
    """Test memory search with error."""
    mock_memory_service.search_memories.side_effect = Exception("API error")

    result = await mcp_server.search_memories("test query")

    assert "Error searching memories" in result
    assert "API error" in result


@pytest.mark.asyncio
async def test_search_memories_service_not_initialized():
    """Test search memories when service not initialized."""
    mcp_server.memory_service = None

    result = await mcp_server.search_memories("test query")

    assert "Error: Memory service not initialized" in result


@pytest.mark.asyncio
async def test_list_memories_success(setup_server_globals, mock_memory_service):
    """Test successful memory listing."""
    mock_memories = [{"id": "mem1", "memory": "Recent memory"}]
    mock_memory_service.get_memories.return_value = mock_memories
    mock_memory_service.format_memories_list.return_value = "Formatted list"

    result = await mcp_server.list_memories(limit=10, user_id="test_user")

    assert result == "Formatted list"
    mock_memory_service.get_memories.assert_called_once_with("test_user", 10)


@pytest.mark.asyncio
async def test_list_memories_empty(setup_server_globals, mock_memory_service):
    """Test listing memories when none exist."""
    mock_memory_service.get_memories.return_value = []

    result = await mcp_server.list_memories()

    assert "No memories found" in result


@pytest.mark.asyncio
async def test_add_memory_success(setup_server_globals, mock_memory_service):
    """Test successful memory addition."""
    mock_memory_service.store_conversation.return_value = "memory_123"

    result = await mcp_server.add_memory("Important note", user_id="test_user")

    assert "Memory stored successfully" in result
    assert "memory_123" in result

    # Verify store_conversation was called with correct parameters
    call_args = mock_memory_service.store_conversation.call_args[1]
    assert call_args["user_id"] == "test_user"
    assert call_args["project_name"] == "manual_memories"
    assert len(call_args["messages"]) == 1
    assert "Important note" in call_args["messages"][0]["content"]


@pytest.mark.asyncio
async def test_add_memory_empty_content(setup_server_globals):
    """Test adding memory with empty content."""
    result = await mcp_server.add_memory("   ", user_id="test_user")

    assert "Error: Content cannot be empty" in result


@pytest.mark.asyncio
async def test_delete_memory_success(setup_server_globals, mock_memory_service):
    """Test successful memory deletion."""
    mock_memory_service.delete_memory.return_value = True

    result = await mcp_server.delete_memory("memory_123")

    assert "deleted successfully" in result
    assert "memory_123" in result
    mock_memory_service.delete_memory.assert_called_once_with("memory_123")


@pytest.mark.asyncio
async def test_delete_memory_failure(setup_server_globals, mock_memory_service):
    """Test memory deletion failure."""
    mock_memory_service.delete_memory.return_value = False

    result = await mcp_server.delete_memory("memory_123")

    assert "Failed to delete" in result
    assert "memory_123" in result


@pytest.mark.asyncio
async def test_delete_memory_empty_id(setup_server_globals):
    """Test deleting memory with empty ID."""
    result = await mcp_server.delete_memory("   ")

    assert "Error: Memory ID cannot be empty" in result


@pytest.mark.asyncio
async def test_analyze_conversations_success(
    setup_server_globals, mock_memory_service, mock_reflection_agent
):
    """Test successful conversation analysis."""
    # Setup mocks
    mock_memories = [{"id": "mem1", "memory": "Test conversation"}]
    mock_memory_service.get_memories.return_value = mock_memories

    mock_analysis = {
        "topics": {"react": 5, "javascript": 3},
        "preferences": ["Prefers TypeScript"],
        "recurring_questions": ["How to debug React?"],
    }
    mock_reflection_agent.analyze_patterns.return_value = mock_analysis
    mock_reflection_agent.generate_insights.return_value = ["Uses React frequently"]

    result = await mcp_server.analyze_conversations(limit=20, user_id="test_user")

    # Verify structure
    assert "## Conversation Analysis" in result
    assert "**Frequent Topics:**" in result
    assert "react (5 mentions)" in result
    assert "**Detected Preferences:**" in result
    assert "Prefers TypeScript" in result
    assert "**Key Insights:**" in result
    assert "Uses React frequently" in result

    # Verify calls
    mock_memory_service.get_memories.assert_called_once_with("test_user", 20)
    mock_reflection_agent.analyze_patterns.assert_called_once_with(mock_memories, 20)


@pytest.mark.asyncio
async def test_analyze_conversations_no_memories(
    setup_server_globals, mock_memory_service
):
    """Test analysis with no memories."""
    mock_memory_service.get_memories.return_value = []

    result = await mcp_server.analyze_conversations()

    assert "No memories available for analysis" in result


@pytest.mark.asyncio
async def test_suggest_next_actions_success(
    setup_server_globals, mock_memory_service, mock_reflection_agent
):
    """Test successful action suggestions."""
    mock_memories = [{"id": "mem1", "memory": "Recent work"}]
    mock_memory_service.get_memories.return_value = mock_memories

    mock_suggestions = [
        "Continue working on React project",
        "Try implementing TypeScript",
        "Review recent debugging session",
    ]
    mock_reflection_agent.suggest_actions.return_value = mock_suggestions

    result = await mcp_server.suggest_next_actions(
        context="React debugging", user_id="test_user"
    )

    assert "## Suggested Next Actions" in result
    assert "Based on your current context: 'React debugging'" in result
    assert "1. Continue working on React project" in result
    assert "2. Try implementing TypeScript" in result
    assert "3. Review recent debugging session" in result

    mock_reflection_agent.suggest_actions.assert_called_once_with(
        "React debugging", mock_memories
    )


@pytest.mark.asyncio
async def test_suggest_next_actions_no_context(
    setup_server_globals, mock_memory_service, mock_reflection_agent
):
    """Test suggestions without specific context."""
    mock_memory_service.get_memories.return_value = [{"memory": "test"}]
    mock_reflection_agent.suggest_actions.return_value = ["General suggestion"]

    result = await mcp_server.suggest_next_actions(user_id="test_user")

    assert "## Suggested Next Actions" in result
    assert "Based on your current context" not in result  # No context provided
    assert "1. General suggestion" in result


@pytest.mark.asyncio
async def test_suggest_next_actions_no_memories(
    setup_server_globals, mock_memory_service
):
    """Test suggestions with no conversation history."""
    mock_memory_service.get_memories.return_value = []

    result = await mcp_server.suggest_next_actions()

    assert "No conversation history available" in result


@pytest.mark.asyncio
async def test_suggest_next_actions_no_suggestions(
    setup_server_globals, mock_memory_service, mock_reflection_agent
):
    """Test when reflection agent returns no suggestions."""
    mock_memory_service.get_memories.return_value = [{"memory": "test"}]
    mock_reflection_agent.suggest_actions.return_value = []

    result = await mcp_server.suggest_next_actions()

    assert "No specific suggestions available" in result


def test_initialize_services():
    """Test service initialization."""
    with (
        patch("mcp_claude_memories.mcp_server.get_settings") as mock_settings,
        patch("mcp_claude_memories.mcp_server.MemoryService") as mock_mem_service,
        patch("mcp_claude_memories.mcp_server.ReflectionAgent") as mock_ref_agent,
    ):
        # Setup mocks
        mock_settings.return_value.mem0_api_key = "test_key"
        mock_mem_instance = Mock()
        mock_ref_instance = Mock()
        mock_mem_service.return_value = mock_mem_instance
        mock_ref_agent.return_value = mock_ref_instance

        # Call function
        mcp_server.initialize_services()

        # Verify
        mock_mem_service.assert_called_once_with("test_key")
        mock_ref_agent.assert_called_once_with(mock_mem_instance)

        assert mcp_server.memory_service == mock_mem_instance
        assert mcp_server.reflection_agent == mock_ref_instance


@pytest.mark.asyncio
async def test_all_tools_handle_service_not_initialized():
    """Test that all tools handle uninitialized services gracefully."""
    # Set services to None
    mcp_server.memory_service = None
    mcp_server.reflection_agent = None

    # Test each tool
    result1 = await mcp_server.search_memories("test")
    assert "Error: Memory service not initialized" in result1

    result2 = await mcp_server.list_memories()
    assert "Error: Memory service not initialized" in result2

    result3 = await mcp_server.add_memory("test")
    assert "Error: Memory service not initialized" in result3

    result4 = await mcp_server.delete_memory("test")
    assert "Error: Memory service not initialized" in result4

    result5 = await mcp_server.analyze_conversations()
    assert "Error: Services not initialized" in result5

    result6 = await mcp_server.suggest_next_actions()
    assert "Error: Services not initialized" in result6

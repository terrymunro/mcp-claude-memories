"""Tests for hook handler module."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from mcp_claude_memories.hook_handler import (
    HookHandler,
    handle_post_tool_use,
    handle_pre_tool_use,
)


@pytest.fixture
def mock_memory_service():
    """Mock memory service for testing."""
    service = Mock()
    service.search_memories = AsyncMock()
    service.get_memories = AsyncMock()
    return service


@pytest.fixture
def mock_reflection_agent():
    """Mock reflection agent for testing."""
    agent = Mock()
    agent.analyze_patterns = AsyncMock()
    agent.suggest_actions = AsyncMock()
    return agent


@pytest.fixture
def hook_handler(mock_memory_service, mock_reflection_agent):
    """Hook handler instance for testing."""
    return HookHandler(mock_memory_service, mock_reflection_agent)


@pytest.fixture
def sample_memories():
    """Sample memory data for testing."""
    return [
        {"id": "mem1", "memory": "debugging React components not rendering properly"},
        {"id": "mem2", "memory": "using TypeScript for better type safety in projects"},
        {"id": "mem3", "memory": "solving authentication issues with JWT tokens"},
    ]


@pytest.mark.asyncio
async def test_handle_hook_event_pre_tool_use(hook_handler, mock_memory_service):
    """Test PreToolUse event handling."""
    context = {"tool_name": "bash", "arguments": {"command": "npm test"}}

    mock_memory_service.search_memories.return_value = [
        {"memory": "running npm test command for testing JavaScript components"}
    ]

    result = await hook_handler.handle_hook_event("PreToolUse", context, "test_user")

    assert result is not None
    assert "💭 Based on our previous discussion" in result


@pytest.mark.asyncio
async def test_handle_hook_event_post_tool_use_success(
    hook_handler, mock_memory_service, mock_reflection_agent
):
    """Test PostToolUse event with successful result."""
    context = {"tool_name": "bash", "result": "Tests passed successfully"}

    mock_memory_service.get_memories.return_value = [{"memory": "test"}]
    mock_reflection_agent.suggest_actions.return_value = [
        "Continue with integration tests"
    ]

    result = await hook_handler.handle_hook_event("PostToolUse", context, "test_user")

    assert result is not None
    assert "💡 Based on your history" in result


@pytest.mark.asyncio
async def test_handle_hook_event_post_tool_use_error(hook_handler, mock_memory_service):
    """Test PostToolUse event with error result."""
    context = {"tool_name": "bash", "result": "Error: command not found"}

    mock_memory_service.search_memories.return_value = [
        {"memory": "debugging command not found errors"}
    ]

    result = await hook_handler.handle_hook_event("PostToolUse", context, "test_user")

    assert result is not None
    assert "💭 Based on our previous discussion" in result
    assert "for troubleshooting" in result


@pytest.mark.asyncio
async def test_handle_hook_event_notification_session_start(
    hook_handler, mock_memory_service, mock_reflection_agent
):
    """Test Notification event for session start."""
    context = {"type": "session_start"}

    mock_memory_service.get_memories.return_value = [
        {"memory": "working on React project with TypeScript"}
    ]
    mock_reflection_agent.analyze_patterns.return_value = {
        "topics": {"react": 5, "typescript": 3}
    }

    result = await hook_handler.handle_hook_event("Notification", context, "test_user")

    assert result is not None
    assert "👋 Welcome back!" in result
    assert "react" in result.lower()


@pytest.mark.asyncio
async def test_handle_hook_event_notification_conversation_start(
    hook_handler, mock_memory_service
):
    """Test Notification event for conversation start."""
    context = {"type": "conversation_start"}

    mock_memory_service.get_memories.return_value = [
        {"memory": "todo: fix authentication bug next"}
    ]

    result = await hook_handler.handle_hook_event("Notification", context, "test_user")

    assert result is not None
    assert "💡 It looks like you have some ongoing work" in result


@pytest.mark.asyncio
async def test_handle_hook_event_unknown_type(hook_handler):
    """Test handling unknown event type."""
    context = {"some": "data"}

    result = await hook_handler.handle_hook_event("UnknownEvent", context)

    assert result is None


@pytest.mark.asyncio
async def test_handle_hook_event_exception(hook_handler, mock_memory_service):
    """Test hook event handling with exception."""
    context = {"tool_name": "test"}

    mock_memory_service.search_memories.side_effect = Exception("API error")

    result = await hook_handler.handle_hook_event("PreToolUse", context)

    assert result is None


def test_should_provide_memory_hint_development_tools(hook_handler):
    """Test memory hint decision for development tools."""
    # Should provide hints for development tools
    assert hook_handler._should_provide_memory_hint("bash", {"command": "npm test"})
    assert hook_handler._should_provide_memory_hint("git", {"command": "git status"})
    assert hook_handler._should_provide_memory_hint("python", {"script": "test.py"})

    # Should not provide hints for non-development tools
    assert not hook_handler._should_provide_memory_hint("unknown_tool", {})


def test_should_provide_memory_hint_file_operations(hook_handler):
    """Test memory hint decision for file operations."""
    # Should provide hints for code files
    assert hook_handler._should_provide_memory_hint(
        "read", {"file_path": "src/component.tsx"}
    )
    assert hook_handler._should_provide_memory_hint("edit", {"file_path": "main.py"})
    assert hook_handler._should_provide_memory_hint(
        "write", {"file_path": "styles.css"}
    )

    # Should not provide hints for non-code files
    assert not hook_handler._should_provide_memory_hint(
        "read", {"file_path": "README.md"}
    )


def test_should_provide_memory_hint_problem_solving_commands(hook_handler):
    """Test memory hint decision for problem-solving commands."""
    # Should provide hints for debugging/testing commands
    assert hook_handler._should_provide_memory_hint("bash", {"command": "debug app"})
    assert hook_handler._should_provide_memory_hint("bash", {"command": "npm test"})
    assert hook_handler._should_provide_memory_hint("bash", {"command": "fix error"})

    # Should not provide hints for basic commands
    assert not hook_handler._should_provide_memory_hint("bash", {"command": "ls"})


def test_extract_search_context(hook_handler):
    """Test search context extraction."""
    # Test with file path
    context = hook_handler._extract_search_context(
        "edit", {"file_path": "src/component.tsx"}, {}
    )
    assert "edit" in context
    assert "typescript react" in context

    # Test with Python file
    context = hook_handler._extract_search_context("read", {"file_path": "main.py"}, {})
    assert "python" in context

    # Test with command
    context = hook_handler._extract_search_context(
        "bash", {"command": "npm run test react"}, {}
    )
    assert "react" in context
    assert "npm" in context


def test_extract_search_context_limits_length(hook_handler):
    """Test that search context is limited in length."""
    context = hook_handler._extract_search_context(
        "very_long_tool_name",
        {"file_path": "very/long/path/to/javascript/file.js"},
        {"extra": "data", "more": "context", "additional": "info"},
    )

    # Should limit to 3 parts
    parts = context.split()
    assert len(parts) <= 3


@pytest.mark.asyncio
async def test_get_relevant_memories(hook_handler, mock_memory_service):
    """Test getting relevant memories."""
    mock_memory_service.search_memories.return_value = [
        {"memory": "React debugging techniques for components"},
        {"memory": "TypeScript best practices for React projects"},
        {"memory": "Vue.js component lifecycle methods"},
    ]

    memories = await hook_handler._get_relevant_memories("react debugging", "test_user")

    assert len(memories) <= 3
    mock_memory_service.search_memories.assert_called_once_with(
        query="react debugging", user_id="test_user", limit=5
    )


@pytest.mark.asyncio
async def test_get_relevant_memories_empty_context(hook_handler):
    """Test getting memories with empty context."""
    memories = await hook_handler._get_relevant_memories("   ", "test_user")

    assert memories == []


@pytest.mark.asyncio
async def test_get_relevant_memories_exception(hook_handler, mock_memory_service):
    """Test getting memories with exception."""
    mock_memory_service.search_memories.side_effect = Exception("API error")

    memories = await hook_handler._get_relevant_memories("test", "test_user")

    assert memories == []


def test_format_memory_hint_single_memory(hook_handler):
    """Test formatting single memory hint."""
    memories = [{"memory": "This is a test memory about React debugging techniques"}]

    result = hook_handler._format_memory_hint(memories, "before testing")

    assert "💭 Based on our previous discussion:" in result
    assert "before testing" in result
    assert len(result) < 200  # Should be limited in length


def test_format_memory_hint_multiple_memories(hook_handler):
    """Test formatting multiple memory hints."""
    memories = [
        {"memory": "First memory about React"},
        {"memory": "Second memory about TypeScript"},
        {"memory": "Third memory should not appear"},
    ]

    result = hook_handler._format_memory_hint(memories, "for context")

    assert "💭 Based on our previous discussions for context:" in result
    assert "1." in result
    assert "2." in result
    assert "Third memory" not in result  # Should limit to 2


def test_format_memory_hint_empty_memories(hook_handler):
    """Test formatting with empty memories."""
    result = hook_handler._format_memory_hint([], "test")

    assert result == ""


def test_indicates_problem(hook_handler):
    """Test problem detection in tool results."""
    # Should detect problems
    assert hook_handler._indicates_problem("Error: command not found")
    assert hook_handler._indicates_problem("Test failed with exception")
    assert hook_handler._indicates_problem("Permission denied")
    assert hook_handler._indicates_problem("404 not found")

    # Should not detect problems
    assert not hook_handler._indicates_problem("Test completed successfully")
    assert not hook_handler._indicates_problem("All systems running")


def test_indicates_success(hook_handler):
    """Test success detection in tool results."""
    # Should detect success
    assert hook_handler._indicates_success("Test completed successfully")
    assert hook_handler._indicates_success("Build created and deployed")
    assert hook_handler._indicates_success("Installation done")

    # Should not detect success
    assert not hook_handler._indicates_success("Error occurred")
    assert not hook_handler._indicates_success("Failed to connect")


@pytest.mark.asyncio
async def test_get_contextual_suggestions(
    hook_handler, mock_memory_service, mock_reflection_agent
):
    """Test getting contextual suggestions."""
    mock_memory_service.get_memories.return_value = [{"memory": "test memory"}]
    mock_reflection_agent.suggest_actions.return_value = [
        "Continue with testing",
        "Review the implementation",
        "Consider optimization",
    ]

    suggestions = await hook_handler._get_contextual_suggestions("bash", "test_user")

    assert len(suggestions) <= 2
    mock_reflection_agent.suggest_actions.assert_called_once()


@pytest.mark.asyncio
async def test_get_contextual_suggestions_no_memories(
    hook_handler, mock_memory_service
):
    """Test suggestions with no memories."""
    mock_memory_service.get_memories.return_value = []

    suggestions = await hook_handler._get_contextual_suggestions("bash", "test_user")

    assert suggestions == []


@pytest.mark.asyncio
async def test_provide_session_context_with_memories(
    hook_handler, mock_memory_service, mock_reflection_agent
):
    """Test providing session context with existing memories."""
    mock_memory_service.get_memories.return_value = [{"memory": "React project work"}]
    mock_reflection_agent.analyze_patterns.return_value = {
        "topics": {"react": 5, "typescript": 2}
    }

    result = await hook_handler._provide_session_context("test_user")

    assert "👋 Welcome back!" in result
    assert "react" in result


@pytest.mark.asyncio
async def test_provide_session_context_no_memories(hook_handler, mock_memory_service):
    """Test providing session context with no memories."""
    mock_memory_service.get_memories.return_value = []

    result = await hook_handler._provide_session_context("test_user")

    assert "👋 Welcome back!" in result
    assert "No previous conversation history found" in result


@pytest.mark.asyncio
async def test_provide_session_context_exception(hook_handler, mock_memory_service):
    """Test session context with exception."""
    mock_memory_service.get_memories.side_effect = Exception("API error")

    result = await hook_handler._provide_session_context("test_user")

    assert result is None


@pytest.mark.asyncio
async def test_suggest_conversation_continuation_todo_pattern(
    hook_handler, mock_memory_service
):
    """Test conversation continuation with TODO pattern."""
    mock_memory_service.get_memories.return_value = [
        {"memory": "todo: finish the authentication feature next"}
    ]

    result = await hook_handler._suggest_conversation_continuation("test_user")

    assert "💡 It looks like you have some ongoing work" in result


@pytest.mark.asyncio
async def test_suggest_conversation_continuation_error_pattern(
    hook_handler, mock_memory_service
):
    """Test conversation continuation with error pattern."""
    mock_memory_service.get_memories.return_value = [
        {"memory": "encountered error with database connection"}
    ]

    result = await hook_handler._suggest_conversation_continuation("test_user")

    assert "🔧 I see you were working through some issues" in result


@pytest.mark.asyncio
async def test_suggest_conversation_continuation_no_patterns(
    hook_handler, mock_memory_service
):
    """Test conversation continuation with no recognizable patterns."""
    mock_memory_service.get_memories.return_value = [
        {"memory": "discussed general React concepts"}
    ]

    result = await hook_handler._suggest_conversation_continuation("test_user")

    assert result is None


@pytest.mark.asyncio
async def test_suggest_conversation_continuation_no_memories(
    hook_handler, mock_memory_service
):
    """Test conversation continuation with no memories."""
    mock_memory_service.get_memories.return_value = []

    result = await hook_handler._suggest_conversation_continuation("test_user")

    assert result is None


@pytest.mark.asyncio
async def test_handle_pre_tool_use_convenience_function():
    """Test the convenience function for pre-tool-use."""
    with (
        patch("mcp_claude_memories.hook_handler.get_settings") as mock_settings,
        patch("mcp_claude_memories.hook_handler.MemoryService"),
        patch("mcp_claude_memories.hook_handler.ReflectionAgent"),
        patch("mcp_claude_memories.hook_handler.HookHandler") as mock_handler_class,
    ):
        # Setup mocks
        mock_settings.return_value.mem0_api_key = "test_key"
        mock_settings.return_value.default_user_id = "test_user"

        mock_handler = Mock()
        mock_handler.handle_hook_event = AsyncMock(return_value="test response")
        mock_handler_class.return_value = mock_handler

        # Call function
        result = await handle_pre_tool_use("bash", {"command": "test"})

        # Verify
        assert result == "test response"
        mock_handler.handle_hook_event.assert_called_once_with(
            "PreToolUse",
            {"tool_name": "bash", "arguments": {"command": "test"}},
            "test_user",
        )


@pytest.mark.asyncio
async def test_handle_post_tool_use_convenience_function():
    """Test the convenience function for post-tool-use."""
    with (
        patch("mcp_claude_memories.hook_handler.get_settings") as mock_settings,
        patch("mcp_claude_memories.hook_handler.MemoryService"),
        patch("mcp_claude_memories.hook_handler.ReflectionAgent"),
        patch("mcp_claude_memories.hook_handler.HookHandler") as mock_handler_class,
    ):
        # Setup mocks
        mock_settings.return_value.mem0_api_key = "test_key"
        mock_settings.return_value.default_user_id = "test_user"

        mock_handler = Mock()
        mock_handler.handle_hook_event = AsyncMock(return_value="test response")
        mock_handler_class.return_value = mock_handler

        # Call function
        result = await handle_post_tool_use("bash", "Success!")

        # Verify
        assert result == "test response"
        mock_handler.handle_hook_event.assert_called_once_with(
            "PostToolUse",
            {"tool_name": "bash", "result": "Success!"},
            "test_user",
        )


@pytest.mark.asyncio
async def test_convenience_functions_handle_exceptions():
    """Test that convenience functions handle exceptions gracefully."""
    with patch("mcp_claude_memories.hook_handler.get_settings") as mock_settings:
        mock_settings.side_effect = Exception("Settings error")

        result1 = await handle_pre_tool_use("test", {})
        result2 = await handle_post_tool_use("test", "result")

        assert result1 is None
        assert result2 is None


def test_hook_handler_initialization(mock_memory_service, mock_reflection_agent):
    """Test HookHandler initialization."""
    with patch("mcp_claude_memories.hook_handler.get_settings") as mock_settings:
        mock_settings.return_value.mem0_api_key = "test_key"

        handler = HookHandler(mock_memory_service, mock_reflection_agent)

        assert handler.memory_service == mock_memory_service
        assert handler.reflection_agent == mock_reflection_agent
        assert handler.settings is not None


@pytest.mark.asyncio
async def test_handle_pre_tool_use_no_hint_needed(hook_handler):
    """Test pre-tool-use when no hint is needed."""
    context = {"tool_name": "unknown_tool", "arguments": {}}

    result = await hook_handler._handle_pre_tool_use(context, "test_user")

    assert result is None


@pytest.mark.asyncio
async def test_handle_pre_tool_use_no_memories(hook_handler, mock_memory_service):
    """Test pre-tool-use when no relevant memories found."""
    context = {"tool_name": "bash", "arguments": {"command": "test"}}

    mock_memory_service.search_memories.return_value = []

    result = await hook_handler._handle_pre_tool_use(context, "test_user")

    assert result is None


@pytest.mark.asyncio
async def test_handle_post_tool_use_neutral_result(hook_handler):
    """Test post-tool-use with neutral result (neither success nor error)."""
    context = {"tool_name": "read", "result": "File contents displayed"}

    result = await hook_handler._handle_post_tool_use(context, "test_user")

    assert result is None

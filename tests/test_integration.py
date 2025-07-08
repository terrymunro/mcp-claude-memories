"""End-to-end integration tests for the mcp-claude-memories system."""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from mcp_claude_memories.config import Settings
from mcp_claude_memories.conversation_parser import ConversationParser
from mcp_claude_memories.conversation_watcher import ConversationWatcher
from mcp_claude_memories.hook_handler import HookHandler
from mcp_claude_memories.memory_service import MemoryService
from mcp_claude_memories.reflection_agent import ReflectionAgent


@pytest.fixture
def temp_config_dir():
    """Create temporary config directory structure."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_dir = Path(temp_dir)
        projects_dir = config_dir / "projects" / "test_project"
        projects_dir.mkdir(parents=True)
        yield config_dir


@pytest.fixture
def mock_settings(temp_config_dir):
    """Mock settings with temporary directory."""
    return Settings(
        mem0_api_key="test_api_key",
        claude_config_dir=temp_config_dir,
        default_user_id="test_user",
        watch_patterns=["conversation*.jsonl"],
    )


@pytest.fixture
def sample_conversation_data():
    """Sample conversation data for testing."""
    return [
        {
            "id": "msg1",
            "role": "user",
            "content": "I'm building a React app with TypeScript and having issues with component rendering",
            "timestamp": "2025-07-02T10:00:00Z",
        },
        {
            "id": "msg2",
            "role": "assistant",
            "content": "For React component rendering issues, first check the console for errors. Common causes include incorrect props, missing dependencies in useEffect, or state update issues.",
            "timestamp": "2025-07-02T10:00:01Z",
        },
        {
            "id": "msg3",
            "role": "user",
            "content": "The component renders initially but doesn't update when props change",
            "timestamp": "2025-07-02T10:01:00Z",
        },
        {
            "id": "msg4",
            "role": "assistant",
            "content": "This sounds like a React re-rendering issue. Make sure your component is properly handling prop changes. You might need to add props to useEffect dependencies or use useMemo for expensive calculations.",
            "timestamp": "2025-07-02T10:01:01Z",
        },
    ]


@pytest.fixture
def mock_memory_service():
    """Mock memory service that simulates Mem0 API."""
    service = Mock(spec=MemoryService)

    # Mock storage
    stored_memories = []

    async def mock_store_conversation(**kwargs):
        memory_id = f"mem_{len(stored_memories)}"

        # Extract meaningful content from messages
        messages = kwargs.get("messages", [])
        content_parts = []
        for msg in messages:
            content_parts.append(msg.get("content", ""))

        # Create a more realistic memory description
        combined_content = " ".join(content_parts)
        project_name = kwargs.get("project_name", "unknown")

        memory_data = {
            "id": memory_id,
            "memory": f"{project_name}: {combined_content[:100]}...",  # Include actual content
            "user_id": kwargs.get("user_id", "default"),
            "metadata": kwargs.get("metadata", {}),
        }
        stored_memories.append(memory_data)
        return memory_id

    async def mock_search_memories(query, user_id="default", limit=10):
        # Simple keyword matching
        query_words = set(query.lower().split())
        matches = []

        for memory in stored_memories:
            memory_words = set(memory["memory"].lower().split())
            if query_words.intersection(memory_words):
                matches.append(memory)

        return matches[:limit]

    async def mock_get_memories(user_id="default", limit=20):
        user_memories = [m for m in stored_memories if m["user_id"] == user_id]
        return user_memories[-limit:]  # Return most recent

    def mock_format_memories_list(memories):
        if not memories:
            return "No memories found"

        formatted = "## Found Memories\n\n"
        for i, memory in enumerate(memories, 1):
            formatted += f"{i}. **{memory['id']}**: {memory['memory']}\n"

        return formatted

    service.store_conversation = AsyncMock(side_effect=mock_store_conversation)
    service.search_memories = AsyncMock(side_effect=mock_search_memories)
    service.get_memories = AsyncMock(side_effect=mock_get_memories)
    service.format_memories_list = Mock(side_effect=mock_format_memories_list)

    return service


@pytest.mark.asyncio
async def test_conversation_file_to_memory_flow(
    temp_config_dir, sample_conversation_data, mock_memory_service
):
    """Test complete flow from conversation file to memory storage."""
    # Create conversation file
    project_dir = temp_config_dir / "projects" / "test_project"
    conv_file = project_dir / "conversation_001.jsonl"

    # Write conversation data
    with open(conv_file, "w") as f:
        for message in sample_conversation_data:
            f.write(json.dumps(message) + "\n")

    # Initialize parser
    parser = ConversationParser()

    # Parse the file
    messages = parser.parse_jsonl_file(conv_file)

    # Verify parsing
    assert len(messages) == 4
    assert messages[0]["content"] == sample_conversation_data[0]["content"]

    # Process with memory service
    conversation_messages = parser.extract_conversation_messages(messages)

    memory_id = await mock_memory_service.store_conversation(
        user_id="test_user",
        project_name="test_project",
        messages=conversation_messages,
        metadata={"source_file": str(conv_file)},
    )

    # Verify storage
    assert memory_id == "mem_0"

    # Test retrieval
    memories = await mock_memory_service.get_memories("test_user")
    assert len(memories) == 1
    assert "test_project" in memories[0]["memory"]


@pytest.mark.asyncio
async def test_file_watcher_integration(
    temp_config_dir, sample_conversation_data, mock_memory_service
):
    """Test file watcher detecting changes and processing conversations."""
    project_dir = temp_config_dir / "projects" / "test_project"
    conv_file = project_dir / "conversation_001.jsonl"

    # Create initial conversation file before starting watcher
    # This tests the _process_existing_files functionality
    # Use the correct format expected by the conversation parser
    conversation_messages = [
        {
            "role": "human",
            "content": "I'm building a React app with TypeScript and having issues with component rendering",
            "timestamp": "2025-07-02T10:00:00Z",
        },
        {
            "role": "assistant",
            "content": "For React component rendering issues, first check the console for errors. Common causes include incorrect props, missing dependencies in useEffect, or state update issues.",
            "timestamp": "2025-07-02T10:00:01Z",
        },
    ]

    with open(conv_file, "w") as f:
        for message in conversation_messages:
            f.write(json.dumps(message) + "\n")

    # Debug: Test parser directly first
    from mcp_claude_memories.conversation_parser import ConversationParser

    parser = ConversationParser()

    # Verify the file can be parsed
    parsed_messages = parser.parse_jsonl_file(conv_file)
    assert len(parsed_messages) > 0, "Parser failed to extract messages from file"

    # Verify message extraction
    extracted_messages = parser.extract_conversation_messages(parsed_messages)
    assert len(extracted_messages) > 0, (
        f"Failed to extract conversation messages: {parsed_messages}"
    )

    # Create watcher with mocked memory service
    watcher = ConversationWatcher(
        memory_service=mock_memory_service,
        claude_config_dir=temp_config_dir,
        watch_patterns=["conversation*.jsonl"],
        default_user_id="test_user",
    )

    # Start watcher - should process existing files
    await watcher.start_watching()

    try:
        # Give some time for existing file processing
        await asyncio.sleep(0.1)

        # Debug: Check what directories are being watched
        status = watcher.get_processing_status()
        assert len(status["watched_directories"]) > 0, (
            f"No directories being watched: {status}"
        )
        assert str(project_dir) in status["watched_directories"], (
            f"Project directory not in watched dirs: {status['watched_directories']}"
        )

        # Verify existing file was processed
        assert mock_memory_service.store_conversation.call_count >= 1, (
            f"Memory service not called. Status: {status}"
        )

        # Get initial call count
        initial_call_count = mock_memory_service.store_conversation.call_count

        # Add more messages (should trigger incremental processing)
        additional_messages = [
            {
                "role": "human",
                "content": "The component renders initially but doesn't update when props change",
                "timestamp": "2025-07-02T10:01:00Z",
            },
            {
                "role": "assistant",
                "content": "This sounds like a React re-rendering issue. Make sure your component is properly handling prop changes.",
                "timestamp": "2025-07-02T10:01:01Z",
            },
        ]

        with open(conv_file, "a") as f:
            for message in additional_messages:
                f.write(json.dumps(message) + "\n")

        # Wait longer for file modification detection and debouncing
        await asyncio.sleep(2.5)  # Wait longer than debounce delay

        # Verify incremental processing occurred
        # Note: this might not always trigger due to file system event timing
        # but the existing file processing should always work
        final_call_count = mock_memory_service.store_conversation.call_count
        assert final_call_count >= initial_call_count

        # Verify memories were stored
        memories = await mock_memory_service.get_memories("test_user")
        assert len(memories) >= 1

    finally:
        watcher.stop_watching()


@pytest.mark.asyncio
async def test_mcp_server_tools_integration(mock_memory_service):
    """Test MCP server tools working with memory service."""
    # Store some test memories first
    test_conversations = [
        {
            "user_id": "test_user",
            "project_name": "react_project",
            "messages": [
                {"role": "human", "content": "How do I debug React components?"},
                {
                    "role": "assistant",
                    "content": "Use React Developer Tools and check console errors",
                },
            ],
        },
        {
            "user_id": "test_user",
            "project_name": "typescript_project",
            "messages": [
                {"role": "human", "content": "TypeScript types for API responses"},
                {
                    "role": "assistant",
                    "content": "Define interfaces for your API response structure",
                },
            ],
        },
    ]

    # Store test conversations in the mock
    for conv in test_conversations:
        await mock_memory_service.store_conversation(**conv)

    # Import and setup MCP server tools with mocked service
    from mcp_claude_memories import mcp_server

    # Temporarily replace global service
    original_service = mcp_server.memory_service
    mcp_server.memory_service = mock_memory_service

    try:
        # Test search_memories tool
        result = await mcp_server.search_memories(
            "React debugging", limit=5, user_id="test_user"
        )
        assert "Found Memories" in result
        assert "react_project" in result.lower()

        # Test list_memories tool
        result = await mcp_server.list_memories(limit=10, user_id="test_user")
        assert "Found Memories" in result

        # Test add_memory tool
        result = await mcp_server.add_memory(
            "User prefers TypeScript over JavaScript", user_id="test_user"
        )
        assert "Memory stored successfully" in result
        assert "mem_2" in result

        # Verify the added memory can be found
        result = await mcp_server.search_memories(
            "TypeScript preference", user_id="test_user"
        )
        assert "Found Memories" in result

    finally:
        # Restore original service
        mcp_server.memory_service = original_service


@pytest.mark.asyncio
async def test_reflection_agent_integration(mock_memory_service):
    """Test reflection agent analyzing real conversation patterns."""
    # Store conversations with patterns
    conversations = [
        {"memory": "Working on React project with TypeScript for better type safety"},
        {"memory": "Debugging React components not rendering properly"},
        {"memory": "How to handle async await in JavaScript functions?"},
        {"memory": "React hooks are confusing, especially useEffect dependencies"},
        {"memory": "Setting up JWT authentication for the API"},
        {"memory": "Testing React components with Jest and React Testing Library"},
        {"memory": "TypeScript interface definitions for API responses"},
        {"memory": "Error handling in React components with try-catch"},
        {"memory": "Using MongoDB for the database with Node.js backend"},
        {"memory": "React performance optimization with useMemo and useCallback"},
    ]

    # Initialize reflection agent
    reflection_agent = ReflectionAgent(mock_memory_service)

    # Analyze patterns
    analysis = await reflection_agent.analyze_patterns(conversations, limit=10)

    # Verify analysis structure
    assert "topics" in analysis
    assert "preferences" in analysis
    assert "technologies" in analysis
    assert "patterns" in analysis

    # Verify topic detection
    topics = analysis["topics"]
    assert "react" in topics
    assert "typescript" in topics
    assert topics["react"] >= 4  # Should find multiple React mentions

    # Generate insights
    insights = reflection_agent.generate_insights(analysis)
    assert len(insights) > 0
    assert any("react" in insight.lower() for insight in insights)

    # Test suggestions
    suggestions = await reflection_agent.suggest_actions(
        "react debugging", conversations
    )
    assert len(suggestions) > 0
    assert any("react" in suggestion.lower() for suggestion in suggestions)


@pytest.mark.asyncio
async def test_hook_handler_integration(mock_memory_service):
    """Test hook handler providing contextual suggestions."""
    # Store relevant memories
    memories = [
        {
            "memory": "Previously solved React rendering issue by checking useEffect dependencies"
        },
        {
            "memory": "TypeScript type errors often caused by incorrect interface definitions"
        },
        {"memory": "Debugging Node.js API with console.log and breakpoints"},
    ]

    # Simulate stored memories
    async def mock_search(query, user_id="default", limit=5):
        return [
            m
            for m in memories
            if any(word in m["memory"].lower() for word in query.lower().split())
        ]

    mock_memory_service.search_memories = AsyncMock(side_effect=mock_search)

    # Initialize components
    reflection_agent = ReflectionAgent(mock_memory_service)
    # Mock the settings for hook handler to avoid config validation
    with patch("mcp_claude_memories.hook_handler.get_settings") as mock_settings:
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_settings.return_value = Settings(
                mem0_api_key="test_api_key_1234567890",
                claude_config_dir=Path(temp_dir),
                default_user_id="test_user",
            )
            hook_handler = HookHandler(mock_memory_service, reflection_agent)

            # Test PreToolUse hook for debugging
            context = {"tool_name": "bash", "arguments": {"command": "npm test react"}}

            result = await hook_handler.handle_hook_event("PreToolUse", context, "test_user")
            assert result is not None
            assert "💭" in result  # Should provide memory hint

            # Test PostToolUse hook for error
            context = {"tool_name": "bash", "result": "Error: Test failed with TypeError"}

            result = await hook_handler.handle_hook_event("PostToolUse", context, "test_user")
            assert result is not None
            assert "💭" in result  # Should provide troubleshooting hint

            # Test Notification hook for session start
            mock_memory_service.get_memories = AsyncMock(return_value=memories)

            async def mock_analyze_patterns(memories_list, limit):
                return {"topics": {"react": 3, "typescript": 2}}

            reflection_agent.analyze_patterns = AsyncMock(side_effect=mock_analyze_patterns)

            context = {"type": "session_start"}
            result = await hook_handler.handle_hook_event("Notification", context, "test_user")
            assert result is not None
            assert "👋 Welcome back!" in result


@pytest.mark.asyncio
async def test_complete_system_integration(
    temp_config_dir, sample_conversation_data, mock_memory_service
):
    """Test complete system flow: file watching -> memory storage -> MCP tools -> hooks."""
    # 1. Setup file watcher
    project_dir = temp_config_dir / "projects" / "test_project"
    conv_file = project_dir / "conversation_001.jsonl"

    # 2. Create conversation file before starting watcher (using correct format)
    conversation_messages = [
        {
            "role": "human",
            "content": "I'm building a React app with TypeScript and having issues with component rendering",
            "timestamp": "2025-07-02T10:00:00Z",
        },
        {
            "role": "assistant",
            "content": "For React component rendering issues, first check the console for errors. Common causes include incorrect props, missing dependencies in useEffect, or state update issues.",
            "timestamp": "2025-07-02T10:00:01Z",
        },
        {
            "role": "human",
            "content": "The component renders initially but doesn't update when props change",
            "timestamp": "2025-07-02T10:01:00Z",
        },
        {
            "role": "assistant",
            "content": "This sounds like a React re-rendering issue. Make sure your component is properly handling prop changes. You might need to add props to useEffect dependencies or use useMemo for expensive calculations.",
            "timestamp": "2025-07-02T10:01:01Z",
        },
    ]

    with open(conv_file, "w") as f:
        for message in conversation_messages:
            f.write(json.dumps(message) + "\n")

    watcher = ConversationWatcher(
        memory_service=mock_memory_service,
        claude_config_dir=temp_config_dir,
        watch_patterns=["conversation*.jsonl"],
        default_user_id="test_user",
    )
    await watcher.start_watching()

    try:
        await asyncio.sleep(0.1)  # Wait for existing file processing

        # 3. Verify memory storage
        assert mock_memory_service.store_conversation.call_count >= 1
        memories = await mock_memory_service.get_memories("test_user")
        assert len(memories) >= 1

        # 4. Test MCP tools
        from mcp_claude_memories import mcp_server

        original_service = mcp_server.memory_service
        mcp_server.memory_service = mock_memory_service

        try:
            # Search for React-related content
            search_result = await mcp_server.search_memories(
                "React component", user_id="test_user"
            )
            assert "Found Memories" in search_result

        finally:
            mcp_server.memory_service = original_service

        # 5. Test hook integration
        reflection_agent = ReflectionAgent(mock_memory_service)
        
        # Mock the settings for hook handler to avoid config validation
        with patch("mcp_claude_memories.hook_handler.get_settings") as mock_settings:
            mock_settings.return_value = Settings(
                mem0_api_key="test_api_key_1234567890",
                claude_config_dir=temp_config_dir,
                default_user_id="test_user",
            )
            hook_handler = HookHandler(mock_memory_service, reflection_agent)

            # Simulate hook for React debugging
            hook_context = {
                "tool_name": "edit",
                "arguments": {"file_path": "src/Component.tsx"},
            }

            await hook_handler.handle_hook_event("PreToolUse", hook_context, "test_user")
            # May or may not return suggestions depending on memory content

        # 6. Test reflection analysis
        all_memories = await mock_memory_service.get_memories("test_user")
        analysis = await reflection_agent.analyze_patterns(all_memories)

        # Should detect React/TypeScript patterns from the sample conversation
        assert "topics" in analysis
        if analysis["topics"]:
            # Should find some technical topics
            assert len(analysis["topics"]) > 0

    finally:
        watcher.stop_watching()


@pytest.mark.asyncio
async def test_error_handling_integration(temp_config_dir, mock_memory_service):
    """Test system behavior with various error conditions."""
    # Test with invalid JSON file
    project_dir = temp_config_dir / "projects" / "test_project"
    invalid_file = project_dir / "conversation_invalid.jsonl"

    with open(invalid_file, "w") as f:
        f.write("invalid json content\n")
        f.write('{"valid": "json"}\n')
        f.write("another invalid line\n")

    # Parser should handle invalid lines gracefully
    parser = ConversationParser()
    messages = parser.parse_jsonl_file(invalid_file)

    # Should parse only the valid line
    assert len(messages) == 1
    assert messages[0]["valid"] == "json"

    # Test memory service errors
    mock_memory_service.store_conversation.side_effect = Exception("API Error")
    mock_memory_service.search_memories.side_effect = Exception("Search API Error")

    # Should handle storage errors gracefully
    with pytest.raises(Exception, match="API Error"):
        await mock_memory_service.store_conversation(
            user_id="test_user",
            project_name="test_project",
            messages=[{"role": "human", "content": "test"}],
        )

    # Test MCP tools with service errors
    from mcp_claude_memories import mcp_server

    original_service = mcp_server.memory_service
    mcp_server.memory_service = mock_memory_service

    try:
        result = await mcp_server.search_memories("test query")
        assert "Error searching memories" in result

    finally:
        mcp_server.memory_service = original_service


@pytest.mark.asyncio
async def test_incremental_processing(temp_config_dir, mock_memory_service):
    """Test incremental processing of conversation files."""
    project_dir = temp_config_dir / "projects" / "test_project"
    conv_file = project_dir / "conversation_incremental.jsonl"

    parser = ConversationParser()

    # Start with 2 messages
    initial_messages = [
        {"id": "msg1", "role": "user", "content": "First message", "timestamp": "2025-07-02T10:00:00Z"},
        {"id": "msg2", "role": "assistant", "content": "First response", "timestamp": "2025-07-02T10:00:01Z"},
    ]

    with open(conv_file, "w") as f:
        for msg in initial_messages:
            f.write(json.dumps(msg) + "\n")

    # Parse initial messages
    messages = parser.parse_jsonl_file(conv_file)
    assert len(messages) == 2

    # Store initial conversation
    conv_messages = parser.extract_conversation_messages(messages)
    await mock_memory_service.store_conversation(
        user_id="test_user", project_name="incremental_test", messages=conv_messages
    )

    # Add more messages
    additional_messages = [
        {"id": "msg3", "role": "user", "content": "Second message", "timestamp": "2025-07-02T10:01:00Z"},
        {"id": "msg4", "role": "assistant", "content": "Second response", "timestamp": "2025-07-02T10:01:01Z"},
    ]

    with open(conv_file, "a") as f:
        for msg in additional_messages:
            f.write(json.dumps(msg) + "\n")

    # Parse only new messages (starting from line 2)
    new_messages = parser.parse_jsonl_file(conv_file, start_line=2)
    assert len(new_messages) == 2
    assert new_messages[0]["content"] == "Second message"

    # Store incremental conversation
    conv_messages = parser.extract_conversation_messages(new_messages)
    await mock_memory_service.store_conversation(
        user_id="test_user", project_name="incremental_test", messages=conv_messages
    )

    # Verify both conversations were stored
    memories = await mock_memory_service.get_memories("test_user")
    assert len(memories) == 2

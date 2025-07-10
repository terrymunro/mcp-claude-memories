# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Essential Commands

### Development Commands
```bash
# Install dependencies
uv sync

# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_memory_service.py

# Run single test function
uv run pytest tests/test_integration.py::test_file_watcher_integration -xvs

# Lint and format code
uv run ruff check
uv run ruff format

# Run with coverage (85% minimum required)
uv run pytest --cov=mcp_claude_memories --cov-fail-under=85
```

### Running the System
```bash
# Start file watcher service
uv run python main.py

# Run MCP server (for manual testing)
uv run mcp-claude-memories

# Debug mode
DEBUG=true uv run python main.py
```

## Core Architecture

This system provides intelligent memory for Claude Code through automatic conversation file monitoring and storage in Mem0 SaaS. The architecture follows a clean separation pattern:

### Data Flow
```
~/.config/claude/projects/*/conversation*.jsonl
                ↓ (file watching)
        ConversationWatcher
                ↓ (parsing)
        ConversationParser
                ↓ (storage)
         MemoryService (Mem0)
                ↓ (analysis)
        ReflectionAgent
                ↓ (delivery)
    HookHandler + MCP Server → Claude Code
```

### Core Components

**ConversationWatcher** (`conversation_watcher.py`)
- Monitors Claude config directories using watchdog
- Handles incremental file processing with 2-second debouncing
- Tracks file positions to avoid reprocessing
- Processes existing files on startup, then monitors for changes

**ConversationParser** (`conversation_parser.py`) 
- Parses JSONL conversation files line by line
- Extracts messages with `role` (human/assistant) and `content` fields
- Filters out system messages and metadata entries
- Handles malformed JSON gracefully with logging

**MemoryService** (`memory_service.py`)
- Interfaces with Mem0 SaaS API for memory storage/retrieval  
- Stores conversations with project context and metadata
- Provides search, list, add, delete operations
- Formats memory responses for MCP tools

**ReflectionAgent** (`reflection_agent.py`)
- Analyzes conversation patterns to identify topics, preferences, technologies
- Generates insights about user working patterns and learning progression
- Provides personalized suggestions for next actions
- Tracks recurring questions and technical patterns

**HookHandler** (`hook_handler.py`)
- Provides proactive memory delivery through Claude Code hooks
- PreToolUse: Contextual hints before tool execution
- PostToolUse: Follow-up suggestions after tool completion  
- Notification: Session context and conversation continuation
- Smart filtering to avoid noise (only provides hints for development activities)

**MCP Server** (`mcp_server.py`)
- Exposes 6 memory tools via FastMCP framework
- Tools: search_memories, list_memories, add_memory, delete_memory, analyze_conversations, suggest_next_actions
- Handles errors gracefully with user-friendly messages
- Global service initialization pattern

## Critical Implementation Details

### Conversation File Format
The parser expects JSONL files with this structure (Claude Code's actual format):
```json
{"type": "user", "content": "message text", "timestamp": "2025-07-02T10:00:00Z"}
{"type": "assistant", "content": "response text", "timestamp": "2025-07-02T10:00:01Z"}
```

**Important**: The parser supports both `type` (Claude Code's actual format) and `role` (legacy format) fields. The parser maps `"user"` to `"human"` internally for memory service compatibility.

### File Watching Mechanics
- ConversationWatcher uses recursive=False watching on project directories
- 2-second debouncing prevents excessive processing during file writes
- File position tracking enables incremental processing
- Existing files processed via `_process_existing_files()` on startup

### Memory Storage Pattern
- Conversations stored per-project with metadata
- Memory descriptions include project name and content summary
- User-based memory isolation via user_id parameter
- Automatic memory ID generation (mem_0, mem_1, etc.)

### Test Architecture
- Comprehensive mocking of Mem0 API via mock_memory_service fixture
- Integration tests create real files in temporary directories
- File watcher tests require proper timing (await asyncio.sleep) due to debouncing
- Hook handler tests need specific memory content matching relevance scoring

### Configuration Management  
- Pydantic Settings with .env file support
- Required: MEM0_API_KEY (>10 characters for validation)
- Claude config directory defaults to ~/.config/claude
- Watch patterns configurable (default: conversation*.jsonl)

## Development Patterns

### Adding New MCP Tools
1. Add async function with `@mcp.tool()` decorator in mcp_server.py
2. Include comprehensive docstring with examples
3. Handle errors gracefully, return user-friendly strings
4. Add corresponding tests in test_mcp_server.py

### Extending Hook Integration
1. Modify HookHandler._should_provide_memory_hint() for new trigger conditions
2. Update _extract_search_context() for new context types
3. Add hook event handling in handle_hook_event() method
4. Test with realistic mock data that matches relevance scoring

### Testing File Watcher Changes
1. Create files BEFORE starting watcher to test _process_existing_files()
2. Use proper message format with role/content/timestamp fields
3. Allow sufficient sleep time (>2.5s) for debouncing in modification tests
4. Manually populate _watched_dirs for unit tests bypassing startup logic

### Memory Service Extensions
1. All operations should be async and handle Mem0 API errors
2. Maintain user isolation via user_id parameter
3. Format responses consistently using format_memories_list()
4. Add error logging with context for debugging

### Configuration Changes
1. Update Settings class in config.py with field validation
2. Add corresponding environment variables to .env.example
3. Update get_settings() usage across components
4. Test configuration edge cases in test_config.py

This architecture prioritizes simplicity and effectiveness while maintaining clean separation of concerns and comprehensive error handling.
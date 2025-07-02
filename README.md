# MCP Claude Memories

A smart memory system for Claude Code that automatically watches your conversation files and provides context-aware memory retrieval through MCP (Model Context Protocol).

## Overview

This project automatically monitors your Claude Code conversation files and stores them in [Mem0](https://mem0.ai) for intelligent retrieval. It provides:

- **Automatic conversation monitoring** via file watching
- **Intelligent memory storage** using Mem0 SaaS
- **6 powerful MCP tools** for memory search and analysis
- **Proactive hook integration** for contextual suggestions
- **Pattern analysis** to understand your working habits
- **Smart recommendations** based on conversation history

## Features

### 🔄 Automatic File Watching
- Monitors `~/.config/claude/projects/*/conversation*.jsonl` files
- Incremental processing of new messages
- Debounced file updates to handle rapid changes

### 🧠 Intelligent Memory Storage
- Stores conversations in Mem0 with rich metadata
- Project-based organization
- Automatic content summarization

### 🛠️ MCP Tools
1. **search_memories** - Natural language search through conversation history
2. **list_memories** - Browse recent memories chronologically
3. **add_memory** - Manually store important information
4. **delete_memory** - Remove outdated or incorrect memories
5. **analyze_conversations** - Identify patterns and preferences
6. **suggest_next_actions** - Get personalized recommendations

### 🪝 Hook Integration
- **PreToolUse hooks** - Proactive memory hints before tool execution
- **PostToolUse hooks** - Follow-up suggestions after tool completion
- **Notification hooks** - Context on session start and conversation continuation

### 📊 Pattern Analysis
- Technology preferences detection
- Recurring question identification
- Learning progression tracking
- Working pattern insights

## Quick Start

### 1. Installation

```bash
# Clone the repository
git clone <repository-url>
cd mcp-claude-memories

# Install with uv (recommended)
uv sync

# Or with pip
pip install -e .
```

### 2. Configuration

Create a `.env` file in the project root:

```env
# Required: Mem0 SaaS API key
MEM0_API_KEY=your_mem0_api_key_here

# Optional: Custom configuration
CLAUDE_CONFIG_DIR=/path/to/claude/config  # defaults to ~/.config/claude
DEFAULT_USER_ID=your_user_id              # defaults to "default_user"
DEBUG=false                               # set to true for debug logging
```

Get your Mem0 API key from [https://app.mem0.ai](https://app.mem0.ai).

### 3. Running the System

#### Background File Watcher

Start the conversation file watcher:

```bash
# Using uv
uv run python main.py

# Or directly
python main.py
```

This will monitor your Claude conversation files and automatically store new conversations in Mem0.

#### MCP Server

Add the MCP server to your Claude Code configuration. In your MCP settings (usually `~/.config/claude/mcp_servers.json`):

```json
{
  "mcp-claude-memories": {
    "command": "uv",
    "args": ["run", "mcp-claude-memories"],
    "cwd": "/path/to/mcp-claude-memories"
  }
}
```

Or if installed globally:

```json
{
  "mcp-claude-memories": {
    "command": "mcp-claude-memories"
  }
}
```

## Usage

### MCP Tools in Claude Code

Once configured, you can use these tools in Claude Code:

#### Search Your Conversation History
```
@search_memories "authentication patterns we discussed"
@search_memories "React debugging approaches"
@search_memories "database design decisions"
```

#### Browse Recent Conversations
```
@list_memories
@list_memories limit=10
```

#### Add Important Notes
```
@add_memory "User prefers TypeScript over JavaScript for type safety"
@add_memory "Project uses Next.js with Tailwind CSS"
```

#### Analyze Your Patterns
```
@analyze_conversations
@analyze_conversations limit=100
```

#### Get Personalized Suggestions
```
@suggest_next_actions
@suggest_next_actions context="React debugging"
```

### Hook Integration

To enable proactive memory delivery, add hooks to your Claude Code configuration:

```json
{
  "hooks": {
    "PreToolUse": {
      "command": "python",
      "args": ["-c", "import asyncio; from mcp_claude_memories.hook_handler import handle_pre_tool_use; print(asyncio.run(handle_pre_tool_use('${tool_name}', ${arguments})) or '')"]
    },
    "PostToolUse": {
      "command": "python", 
      "args": ["-c", "import asyncio; from mcp_claude_memories.hook_handler import handle_post_tool_use; print(asyncio.run(handle_post_tool_use('${tool_name}', '${result}')) or '')"]
    }
  }
}
```

## Configuration Options

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MEM0_API_KEY` | **Required** - Your Mem0 SaaS API key | - |
| `CLAUDE_CONFIG_DIR` | Path to Claude configuration directory | `~/.config/claude` |
| `DEFAULT_USER_ID` | Default user identifier for memories | `default_user` |
| `WATCH_PATTERNS` | File patterns to watch (comma-separated) | `conversation*.jsonl` |
| `DEBUG` | Enable debug logging | `false` |

### File Structure

The system expects Claude conversation files in this structure:
```
~/.config/claude/
└── projects/
    ├── project1/
    │   ├── conversation_001.jsonl
    │   └── conversation_002.jsonl
    └── project2/
        └── conversation_001.jsonl
```

## Development

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=mcp_claude_memories

# Run specific test file
uv run pytest tests/test_memory_service.py
```

### Code Quality

```bash
# Format code
uv run ruff format

# Lint code  
uv run ruff check

# Type checking
uv run mypy mcp_claude_memories
```

### Architecture

The system consists of several key components:

- **ConversationWatcher** - Monitors Claude config directories for file changes
- **ConversationParser** - Parses JSONL conversation files and extracts messages
- **MemoryService** - Interfaces with Mem0 SaaS for memory storage and retrieval
- **ReflectionAgent** - Analyzes conversation patterns and generates insights
- **HookHandler** - Provides proactive memory delivery through Claude Code hooks
- **MCP Server** - Exposes memory functionality as MCP tools

## Troubleshooting

### Common Issues

**"Memory service not initialized" error**
- Check that your `MEM0_API_KEY` is correctly set in `.env`
- Verify the API key is valid at [mem0.ai](https://mem0.ai)

**File watcher not detecting changes**
- Ensure `CLAUDE_CONFIG_DIR` points to the correct directory
- Check file permissions on the Claude config directory
- Verify conversation files follow the expected naming pattern

**MCP tools not appearing in Claude Code**
- Check your MCP server configuration in `~/.config/claude/mcp_servers.json`
- Verify the command path and working directory are correct
- Check Claude Code logs for MCP connection errors

**Hook integration not working**
- Ensure hook commands are properly configured in Claude Code settings
- Check that the Python environment can import the hook handler modules
- Verify environment variables are accessible from hook execution context

### Debug Mode

Enable debug logging by setting `DEBUG=true` in your `.env` file:

```env
DEBUG=true
```

This will provide detailed logs about file watching, memory operations, and MCP tool execution.

### Logs

The file watcher creates a log file: `claude_memories_watcher.log`

Check this file for detailed information about system operation and any errors.

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes and add tests
4. Run the test suite: `uv run pytest`
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [Mem0](https://mem0.ai) for the intelligent memory storage
- [Claude Code](https://claude.ai/code) for the MCP framework
- [FastMCP](https://github.com/jlowin/fastmcp) for the MCP server implementation

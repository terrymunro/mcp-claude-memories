# MCP Claude Memories - Detailed Implementation Plan

**Date:** 2025-07-02  
**Project:** mcp-claude-memories  
**Goal:** Rebuild memory system using file watching + Mem0 + MCP + hooks

## Project Overview

Rebuild the memory system concept from mcp-mitm-mem0 using a direct file-watching approach instead of MITM proxy. The system will monitor Claude conversation files, store memories in Mem0 SaaS, and provide memory access via MCP server with proactive memory delivery through hooks.

## Architecture

```
~/.config/claude/projects/*/conversation*.jsonl
                ↓
          File Watcher → Mem0 SaaS
                ↓
    Reflection Agent (analysis)
                ↓
Claude ← Hooks (proactive) + MCP Server (on-demand)
```

## Key Design Principles

- **Minimal**: 2-3 Python files maximum, tight implementation
- **Focused**: Core memory functionality only, no enterprise features  
- **Simple**: Standard logging, basic error handling, straightforward config
- **Effective**: Well-crafted tool descriptions that guide Claude usage
- **Work First**: Make it functional before optimizing

## Phase 1: Project Foundation (15 mins)

### 1.1 Project Structure ✅
- **File**: `pyproject.toml`
- **Dependencies**: 
  - `mcp` - Model Context Protocol framework
  - `mem0ai` - Memory storage service  
  - `watchdog` - File system monitoring
  - `pydantic-settings` - Configuration management
  - `python-dotenv` - Environment variable loading
- **Dev Dependencies**:
  - `pytest`, `pytest-asyncio`, `pytest-mock` - Testing framework
- **Entry Point**: `mcp-claude-memories = "mcp_claude_memories.mcp_server:main"`

### 1.2 Configuration System
- **File**: `.env.example`
  ```
  MEM0_API_KEY=your_mem0_api_key_here
  CLAUDE_CONFIG_DIR=~/.config/claude
  DEFAULT_USER_ID=default_user
  DEBUG=false
  ```
- **File**: `mcp_claude_memories/config.py`
  - Pydantic Settings class for type-safe configuration
  - Environment variable loading with defaults
  - Path resolution for Claude config directory

### 1.3 Basic Testing Setup
- **Directory**: `tests/`
- **File**: `tests/test_config.py`
  - Test environment loading works
  - Test config validation
  - Test default values

## Phase 2: Mem0 Integration Layer (30 mins)

### 2.1 Memory Service
- **File**: `mcp_claude_memories/memory_service.py`
- **Class**: `MemoryService`
- **Purpose**: Wrapper around Mem0 API for conversation storage

#### Methods:
```python
async def store_conversation(
    user_id: str, 
    project_name: str, 
    messages: List[Dict], 
    metadata: Dict = None
) -> str:
    """Store conversation in Mem0 with structured metadata"""
    
async def search_memories(
    query: str, 
    user_id: str = "default", 
    limit: int = 10
) -> List[Dict]:
    """Search memories using natural language"""
    
async def get_memories(
    user_id: str = "default", 
    limit: int = 20
) -> List[Dict]:
    """Get recent memories chronologically"""
    
async def delete_memory(memory_id: str) -> bool:
    """Remove specific memory by ID"""
```

#### Memory Format:
```python
{
    "user_id": "default_user",
    "project_name": "my-project", 
    "timestamp": "2025-07-02T10:30:00Z",
    "message_type": "user|assistant",
    "content": "The actual message content",
    "metadata": {
        "file_path": "/path/to/conversation.jsonl",
        "line_number": 42,
        "conversation_id": "uuid"
    }
}
```

### 2.2 Conversation Parser
- **File**: `mcp_claude_memories/conversation_parser.py`
- **Class**: `ConversationParser`
- **Purpose**: Parse Claude JSONL conversation files

#### Methods:
```python
def parse_jsonl_file(file_path: str, start_line: int = 0) -> List[Dict]:
    """Parse JSONL file from specific line onwards"""
    
def extract_messages(jsonl_data: List[Dict]) -> List[Dict]:
    """Extract user/assistant messages from JSONL data"""
    
def extract_metadata(file_path: str, jsonl_data: Dict) -> Dict:
    """Extract project name, timestamp, conversation info"""
```

#### JSONL Format Handling:
- Parse each line as JSON object
- Extract `role` and `content` fields
- Handle different message types (text, tool_calls)
- For now, ignore complex tool calls - focus on text messages
- Extract project name from file path

### 2.3 Testing Memory Components
- **File**: `tests/test_memory_service.py`
  - Mock Mem0 API calls using pytest-mock
  - Test successful storage and retrieval
  - Test error handling for API failures
  - Test memory format validation

- **File**: `tests/test_conversation_parser.py`
  - Test JSONL parsing with sample files
  - Test message extraction
  - Test metadata generation
  - Test handling of malformed JSON

## Phase 3: File Watcher System (30 mins)

### 3.1 Simple File Monitor
- **File**: `mcp_claude_memories/conversation_watcher.py`
- **Class**: `ConversationWatcher`
- **Purpose**: Monitor Claude conversation files for changes

#### Core Functionality:
```python
class ConversationWatcher:
    def __init__(self, claude_config_dir: str, memory_service: MemoryService):
        """Initialize with watchdog file system observer"""
        
    async def start_watching(self):
        """Start monitoring conversation files"""
        
    def _on_file_modified(self, event):
        """Handle file modification events"""
        
    async def _process_file_changes(self, file_path: str):
        """Process new content in conversation files"""
```

#### Watch Pattern:
- Monitor: `~/.config/claude/projects/*/conversation*.jsonl`
- Use `watchdog.observers.Observer` with `FileSystemEventHandler`
- Track last processed position for each file to avoid reprocessing
- Debounce file changes (wait for writes to complete)

#### File Processing:
1. Read file from last known position
2. Parse new JSONL lines
3. Extract messages using ConversationParser
4. Store in Mem0 using MemoryService
5. Update last processed position

### 3.2 Background Service Management
- Make watcher runnable as standalone script
- Add `if __name__ == "__main__":` block
- Basic logging for debugging:
  ```python
  import logging
  logging.basicConfig(level=logging.INFO)
  logger = logging.getLogger(__name__)
  ```
- Graceful shutdown with signal handling

### 3.3 File Processing Logic
- **State Tracking**: Remember last processed line for each file
- **Incremental Processing**: Only process new content since last run
- **Error Recovery**: Continue processing other files if one fails
- **Async Integration**: Use asyncio for Mem0 API calls

### 3.4 Testing File Watcher
- **File**: `tests/test_conversation_watcher.py`
  - Create temporary directories and fake JSONL files
  - Test file modification detection
  - Test incremental processing (avoiding reprocessing)
  - Test error handling for invalid files
  - Mock MemoryService calls

## Phase 4: MCP Server Implementation (45 mins)

### 4.1 FastMCP Server Setup
- **File**: `mcp_claude_memories/mcp_server.py`
- **Framework**: FastMCP for simplicity
- **Server Name**: "claude-memories"

```python
from mcp.server.fastmcp import FastMCP
from .memory_service import MemoryService
from .config import Settings

mcp = FastMCP("claude-memories")
```

### 4.2 Core Memory Tools

#### 4.2.1 Search Memories Tool
```python
@mcp.tool()
async def search_memories(
    query: str, 
    limit: int = 10, 
    user_id: str = "default"
) -> str:
    """Search conversation history using natural language. 
    
    Use this when you need context from previous discussions. 
    
    Examples:
    - 'authentication patterns we discussed'
    - 'debugging approaches for React'
    - 'user's coding preferences'
    - 'previous solutions to CORS errors'
    
    Args:
        query: Natural language description of what to find
        limit: Maximum number of memories to return (default: 10)
        user_id: User identifier (default: "default")
    
    Returns:
        Formatted list of relevant memories with context
    """
```

#### 4.2.2 List Recent Memories Tool
```python
@mcp.tool()
async def list_memories(
    limit: int = 20, 
    user_id: str = "default"
) -> str:
    """Browse recent memories chronologically. 
    
    Useful for understanding recent conversation flow and context.
    Shows the most recent memories first.
    
    Args:
        limit: Number of recent memories to show (default: 20)
        user_id: User identifier (default: "default")
    
    Returns:
        Chronological list of recent memories with timestamps
    """
```

#### 4.2.3 Manual Memory Addition Tool
```python
@mcp.tool()
async def add_memory(
    content: str, 
    user_id: str = "default"
) -> str:
    """Manually store important information for future reference.
    
    Use for key decisions, preferences, or insights you want to remember.
    This creates a manual memory that will be included in future searches.
    
    Examples:
    - User preferences: "User prefers TypeScript over JavaScript"
    - Important decisions: "Decided to use React Query for data fetching"
    - Context notes: "Working on e-commerce project with Next.js"
    
    Args:
        content: The information to store
        user_id: User identifier (default: "default")
    
    Returns:
        Confirmation message with memory ID
    """
```

#### 4.2.4 Memory Deletion Tool
```python
@mcp.tool()
async def delete_memory(memory_id: str) -> str:
    """Remove a specific memory by ID.
    
    Use when information is outdated or incorrect.
    Memory IDs can be found in the output of search_memories or list_memories.
    
    Args:
        memory_id: The unique identifier of the memory to delete
    
    Returns:
        Confirmation message of deletion
    """
```

#### 4.2.5 Conversation Analysis Tool
```python
@mcp.tool()
async def analyze_conversations(
    limit: int = 50, 
    user_id: str = "default"
) -> str:
    """Analyze recent conversation patterns to identify topics, preferences, and recurring themes.
    
    Autonomous trigger: Use when user seems to be asking similar questions repeatedly
    or when you want to understand their working patterns.
    
    This tool identifies:
    - Frequently discussed topics
    - Recurring questions or problems
    - User preferences and working style
    - Learning progression and skill gaps
    
    Args:
        limit: Number of recent conversations to analyze (default: 50)
        user_id: User identifier (default: "default")
    
    Returns:
        Analysis report with insights and patterns
    """
```

#### 4.2.6 Next Actions Suggestions Tool
```python
@mcp.tool()
async def suggest_next_actions(
    context: str = "", 
    user_id: str = "default"
) -> str:
    """Get personalized suggestions based on conversation history and patterns.
    
    Autonomous trigger: Use when user asks 'what should I do next?' or seems stuck.
    Also useful when starting a new session to suggest continuing previous work.
    
    This tool provides:
    - Suggestions based on incomplete tasks
    - Next logical steps in ongoing projects
    - Related topics they might want to explore
    - Learning recommendations based on their interests
    
    Args:
        context: Current context or specific area for suggestions (optional)
        user_id: User identifier (default: "default")
    
    Returns:
        Personalized action suggestions with reasoning
    """
```

### 4.3 Tool Implementation Details

#### Error Handling:
```python
try:
    memories = await memory_service.search_memories(query, user_id, limit)
    # Format and return results
except Exception as e:
    return f"Error searching memories: {str(e)}"
```

#### Response Formatting:
- Concise but informative responses
- Include memory IDs for deletion
- Show relevance scores when available
- Format timestamps in human-readable form
- Limit response length to avoid overwhelming Claude

### 4.4 Main Entry Point
```python
def main():
    """Entry point for MCP server"""
    mcp.run()

if __name__ == "__main__":
    main()
```

### 4.5 Testing MCP Tools
- **File**: `tests/test_mcp_server.py`
  - Test each tool individually with mocked MemoryService
  - Test parameter validation and error handling
  - Test response formatting
  - Integration test with FastMCP framework

## Phase 5: Reflection Agent (30 mins)

### 5.1 Simple Pattern Analysis
- **File**: `mcp_claude_memories/reflection_agent.py`
- **Class**: `ReflectionAgent`
- **Purpose**: Analyze conversation patterns and generate insights

#### Core Analysis Methods:
```python
class ReflectionAgent:
    async def analyze_patterns(
        self, 
        memories: List[Dict], 
        limit: int = 50
    ) -> Dict:
        """Analyze conversation memories for patterns"""
        
    def _extract_topics(self, memories: List[Dict]) -> List[str]:
        """Extract frequently discussed topics"""
        
    def _identify_preferences(self, memories: List[Dict]) -> List[str]:
        """Identify user preferences and working style"""
        
    def _find_recurring_questions(self, memories: List[Dict]) -> List[str]:
        """Find questions asked multiple times"""
```

#### Pattern Detection:
1. **Topic Analysis**: 
   - Keywords and phrases that appear frequently
   - Technical terms and technologies mentioned
   - Project contexts and domains

2. **Preference Detection**:
   - Programming languages preferred
   - Code style preferences (functional vs OOP, etc.)
   - Tool and framework preferences
   - Response style preferences (detailed vs concise)

3. **Question Patterns**:
   - Recurring problems or questions
   - Areas where user needs more help
   - Learning progression indicators

### 5.2 Insight Generation
```python
def generate_insights(self, analysis: Dict) -> List[str]:
    """Generate human-readable insights from analysis"""
    
def calculate_confidence(self, pattern_count: int, total_memories: int) -> float:
    """Calculate confidence score for insights"""
```

#### Insight Types:
- **Technical Preferences**: "User prefers TypeScript over JavaScript (85% confidence)"
- **Working Patterns**: "User often works on React projects in the evening"
- **Learning Areas**: "User frequently asks about async/await patterns" 
- **Problem Areas**: "User has recurring CORS issues with API calls"

### 5.3 Memory-Based Suggestions
```python
async def suggest_actions(
    self, 
    context: str, 
    user_memories: List[Dict]
) -> List[str]:
    """Generate contextual suggestions based on memories and current context"""
    
def _find_related_memories(
    self, 
    context: str, 
    memories: List[Dict]
) -> List[Dict]:
    """Find memories related to current context"""
```

#### Suggestion Logic:
1. **Context Matching**: Find memories related to current discussion
2. **Pattern Application**: Apply learned preferences to suggestions
3. **Gap Identification**: Suggest areas for learning or improvement
4. **Project Continuity**: Suggest continuing incomplete tasks

### 5.4 Integration with MCP Tools
- Called by `analyze_conversations` tool
- Called by `suggest_next_actions` tool
- Store insights as special memory types for future reference

### 5.5 Testing Reflection Agent
- **File**: `tests/test_reflection_agent.py`
  - Test pattern detection with sample conversation data
  - Test insight generation and confidence scoring
  - Test suggestion relevance
  - Mock different user types and preferences

## Phase 6: Hook Integration System (30 mins)

### 6.1 Hook Response Generator
- **File**: `mcp_claude_memories/hook_handler.py`
- **Purpose**: Generate responses for Claude Code hooks

#### Core Functions:
```python
async def handle_hook_event(
    event_type: str, 
    context: Dict
) -> Optional[str]:
    """Main hook event handler"""
    
async def get_relevant_memories(context: Dict) -> List[Dict]:
    """Find memories relevant to current conversation context"""
    
async def get_proactive_insights(context: Dict) -> List[str]:
    """Get insights that might be helpful for current context"""
    
def format_hook_response(
    memories: List[Dict], 
    insights: List[str]
) -> str:
    """Format response for Claude Code hook consumption"""
```

### 6.2 Proactive Memory Delivery

#### Context Analysis:
- Extract keywords from current conversation
- Identify technical terms and project context
- Match against stored memory topics

#### Relevance Scoring:
```python
def calculate_relevance_score(
    memory: Dict, 
    context_keywords: List[str]
) -> float:
    """Calculate how relevant a memory is to current context"""
```

#### Response Formatting:
```python
def format_memory_hint(memories: List[Dict]) -> str:
    """Format memories for proactive delivery
    
    Format: 'Based on our previous discussion about X, you might want to consider Y...'
    """
```

### 6.3 Hook Event Types

#### Tool Use Events:
- Trigger when Claude uses certain tools
- Provide relevant memories before tool execution
- Suggest related memories after tool completion

#### Conversation Events:
- Trigger on new conversation start
- Provide context from recent related conversations
- Suggest continuing incomplete tasks

### 6.4 Response Guidelines
- **Concise**: Keep responses short and relevant
- **Contextual**: Only provide memories that match current context
- **Confidence**: Include confidence indicators when uncertain
- **Non-intrusive**: Don't overwhelm with too many memories

### 6.5 Testing Hook System
- **File**: `tests/test_hook_handler.py`
  - Test memory relevance detection with different contexts
  - Test response formatting and length limits
  - Test confidence scoring
  - Mock various conversation contexts

## Phase 7: Integration & Polish (20 mins)

### 7.1 End-to-End Integration Test
- **File**: `tests/test_integration.py`
- **Purpose**: Test complete workflow

#### Test Scenarios:
1. **File to Memory Flow**:
   - Create fake JSONL conversation file
   - Trigger file watcher
   - Verify memory storage in Mem0
   - Search and retrieve memories via MCP

2. **Analysis Flow**:
   - Store sample conversations
   - Run reflection agent analysis
   - Verify pattern detection
   - Test suggestion generation

3. **Hook Flow**:
   - Simulate conversation context
   - Trigger hook handler
   - Verify relevant memory retrieval
   - Test response formatting

### 7.2 Basic Error Handling

#### File Watcher Errors:
- Handle invalid JSONL gracefully
- Continue processing other files if one fails
- Log errors for debugging

#### Mem0 API Errors:
- Handle network failures gracefully
- Provide fallback responses when API unavailable
- Retry logic for transient failures

#### MCP Server Errors:
- Return user-friendly error messages
- Continue serving other tools if one fails
- Log errors for debugging

### 7.3 Simple Documentation
- **File**: `README.md`
- **Sections**:
  - Quick setup instructions
  - Configuration options
  - Basic usage examples
  - Troubleshooting common issues

## Success Criteria

✅ **Conversation Capture**: Claude conversations automatically stored in Mem0  
✅ **Memory Search**: Claude can search and retrieve past conversation context  
✅ **Pattern Analysis**: Reflection agent identifies conversation patterns and preferences  
✅ **Proactive Delivery**: Hook system provides relevant memories without being asked  
✅ **Tool Quality**: MCP tools have excellent descriptions that guide effective usage  
✅ **Test Coverage**: Comprehensive tests covering all core functionality  
✅ **Code Quality**: Simple, maintainable codebase under 800 lines total  
✅ **Integration**: All components work together seamlessly  

## Timeline Estimate: 3 hours

- **Phase 1** (Foundation): 15 minutes
- **Phase 2** (Mem0 Integration): 30 minutes  
- **Phase 3** (File Watcher): 30 minutes
- **Phase 4** (MCP Server): 45 minutes
- **Phase 5** (Reflection Agent): 30 minutes
- **Phase 6** (Hook Integration): 30 minutes
- **Phase 7** (Integration & Polish): 20 minutes

## Implementation Notes

- Keep it simple - avoid over-engineering
- Focus on making it work first, optimize later
- Use standard Python logging, not complex structured logging
- Basic error handling - add more when problems arise
- This is a development tool/experiment, not production system
- Premature optimization is the root of all evil!

## File Structure

```
mcp-claude-memories/
├── plans/
│   └── 2025-07-02-claude-memories.md
├── mcp_claude_memories/
│   ├── __init__.py
│   ├── config.py
│   ├── memory_service.py
│   ├── conversation_parser.py
│   ├── conversation_watcher.py
│   ├── mcp_server.py
│   ├── reflection_agent.py
│   └── hook_handler.py
├── tests/
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_memory_service.py
│   ├── test_conversation_parser.py
│   ├── test_conversation_watcher.py
│   ├── test_mcp_server.py
│   ├── test_reflection_agent.py
│   ├── test_hook_handler.py
│   └── test_integration.py
├── .env.example
├── pyproject.toml
├── README.md
└── main.py (entry point for watcher)
```
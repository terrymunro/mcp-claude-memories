"""MCP server for Claude memories using FastMCP."""

import logging

from mcp.server.fastmcp import FastMCP

from .config import get_settings
from .memory_service import MemoryService
from .reflection_agent import ReflectionAgent

logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("claude-memories")

# Global instances (will be initialized in main())
memory_service: MemoryService | None = None
reflection_agent: ReflectionAgent | None = None


def initialize_services():
    """Initialize global service instances."""
    global memory_service, reflection_agent

    settings = get_settings()

    # Initialize memory service
    memory_service = MemoryService(settings.mem0_api_key)

    # Initialize reflection agent
    reflection_agent = ReflectionAgent(memory_service)

    logger.info("Services initialized successfully")


@mcp.tool()
async def search_memories(query: str, limit: int = 10, user_id: str = "default") -> str:
    """Search conversation history using natural language.

    Use this when you need context from previous discussions.

    Examples:
    - 'authentication patterns we discussed'
    - 'debugging approaches for React'
    - 'user's coding preferences'
    - 'previous solutions to CORS errors'
    - 'typescript patterns we used'
    - 'database design decisions'

    Args:
        query: Natural language description of what to find
        limit: Maximum number of memories to return (default: 10)
        user_id: User identifier (default: "default")

    Returns:
        Formatted list of relevant memories with context
    """
    try:
        if not memory_service:
            return "Error: Memory service not initialized"

        memories = await memory_service.search_memories(query, user_id, limit)

        if not memories:
            return f"No memories found for query: '{query}'"

        return memory_service.format_memories_list(memories)

    except Exception as e:
        logger.error(f"Error searching memories: {e}")
        return f"Error searching memories: {str(e)}"


@mcp.tool()
async def list_memories(limit: int = 20, user_id: str = "default") -> str:
    """Browse recent memories chronologically.

    Useful for understanding recent conversation flow and context.
    Shows the most recent memories first.

    Args:
        limit: Number of recent memories to show (default: 20)
        user_id: User identifier (default: "default")

    Returns:
        Chronological list of recent memories with timestamps
    """
    try:
        if not memory_service:
            return "Error: Memory service not initialized"

        memories = await memory_service.get_memories(user_id, limit)

        if not memories:
            return "No memories found for this user"

        return memory_service.format_memories_list(memories)

    except Exception as e:
        logger.error(f"Error listing memories: {e}")
        return f"Error listing memories: {str(e)}"


@mcp.tool()
async def add_memory(content: str, user_id: str = "default") -> str:
    """Manually store important information for future reference.

    Use for key decisions, preferences, or insights you want to remember.
    This creates a manual memory that will be included in future searches.

    Examples:
    - User preferences: "User prefers TypeScript over JavaScript"
    - Important decisions: "Decided to use React Query for data fetching"
    - Context notes: "Working on e-commerce project with Next.js"
    - Learning notes: "User struggles with async/await patterns"

    Args:
        content: The information to store
        user_id: User identifier (default: "default")

    Returns:
        Confirmation message with memory ID
    """
    try:
        if not memory_service:
            return "Error: Memory service not initialized"

        if not content.strip():
            return "Error: Content cannot be empty"

        # Store as a manual memory
        messages = [{"role": "assistant", "content": f"Manual memory: {content}"}]

        memory_id = await memory_service.store_conversation(
            user_id=user_id,
            project_name="manual_memories",
            messages=messages,
            metadata={"type": "manual", "source": "mcp_tool"},
        )

        return f"Memory stored successfully with ID: {memory_id}"

    except Exception as e:
        logger.error(f"Error adding memory: {e}")
        return f"Error adding memory: {str(e)}"


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
    try:
        if not memory_service:
            return "Error: Memory service not initialized"

        if not memory_id.strip():
            return "Error: Memory ID cannot be empty"

        success = await memory_service.delete_memory(memory_id)

        if success:
            return f"Memory {memory_id} deleted successfully"
        else:
            return f"Failed to delete memory {memory_id} (may not exist)"

    except Exception as e:
        logger.error(f"Error deleting memory: {e}")
        return f"Error deleting memory: {str(e)}"


@mcp.tool()
async def analyze_conversations(limit: int = 50, user_id: str = "default") -> str:
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
    try:
        if not memory_service or not reflection_agent:
            return "Error: Services not initialized"

        # Get recent memories for analysis
        memories = await memory_service.get_memories(user_id, limit)

        if not memories:
            return "No memories available for analysis"

        # Analyze patterns using reflection agent
        analysis = await reflection_agent.analyze_patterns(memories, limit)

        # Generate insights
        insights = reflection_agent.generate_insights(analysis)

        if not insights:
            return "No significant patterns detected in recent conversations"

        # Format response
        response = "## Conversation Analysis\n\n"

        if analysis.get("topics"):
            response += "**Frequent Topics:**\n"
            for topic, count in analysis["topics"].items():
                response += f"- {topic} ({count} mentions)\n"
            response += "\n"

        if analysis.get("preferences"):
            response += "**Detected Preferences:**\n"
            for pref in analysis["preferences"]:
                response += f"- {pref}\n"
            response += "\n"

        if analysis.get("recurring_questions"):
            response += "**Recurring Questions/Issues:**\n"
            for question in analysis["recurring_questions"]:
                response += f"- {question}\n"
            response += "\n"

        response += "**Key Insights:**\n"
        for insight in insights:
            response += f"- {insight}\n"

        return response

    except Exception as e:
        logger.error(f"Error analyzing conversations: {e}")
        return f"Error analyzing conversations: {str(e)}"


@mcp.tool()
async def suggest_next_actions(context: str = "", user_id: str = "default") -> str:
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
    try:
        if not memory_service or not reflection_agent:
            return "Error: Services not initialized"

        # Get recent memories for context
        memories = await memory_service.get_memories(user_id, 30)

        if not memories:
            return "No conversation history available for suggestions"

        # Get suggestions from reflection agent
        suggestions = await reflection_agent.suggest_actions(context, memories)

        if not suggestions:
            return "No specific suggestions available at this time"

        # Format response
        response = "## Suggested Next Actions\n\n"

        if context:
            response += f"Based on your current context: '{context}'\n\n"

        for i, suggestion in enumerate(suggestions, 1):
            response += f"{i}. {suggestion}\n"

        return response

    except Exception as e:
        logger.error(f"Error generating suggestions: {e}")
        return f"Error generating suggestions: {str(e)}"


def main():
    """Main entry point for the MCP server."""
    # Initialize services
    initialize_services()

    # Run the server
    mcp.run()


if __name__ == "__main__":
    main()

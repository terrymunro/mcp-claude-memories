"""Hook handler for proactive memory delivery to Claude Code."""

import logging
import re

from .config import get_settings
from .memory_service import MemoryService
from .reflection_agent import ReflectionAgent

logger = logging.getLogger(__name__)


class HookHandler:
    """Handles Claude Code hook events and provides proactive memory delivery."""

    def __init__(
        self, memory_service: MemoryService, reflection_agent: ReflectionAgent
    ):
        """Initialize hook handler with services."""
        self.memory_service = memory_service
        self.reflection_agent = reflection_agent
        self.settings = get_settings()

    async def handle_hook_event(
        self, event_type: str, context: dict, user_id: str = "default"
    ) -> str | None:
        """Main hook event handler.

        Args:
            event_type: Type of hook event (PreToolUse, PostToolUse, etc.)
            context: Context information from Claude Code
            user_id: User identifier

        Returns:
            Response string for Claude or None if no response needed
        """
        try:
            logger.info(f"Handling hook event: {event_type}")

            if event_type == "PreToolUse":
                return await self._handle_pre_tool_use(context, user_id)
            elif event_type == "PostToolUse":
                return await self._handle_post_tool_use(context, user_id)
            elif event_type == "Notification":
                return await self._handle_notification(context, user_id)
            else:
                logger.debug(f"Unhandled event type: {event_type}")
                return None

        except Exception as e:
            logger.error(f"Error handling hook event: {e}")
            return None

    async def _handle_pre_tool_use(self, context: dict, user_id: str) -> str | None:
        """Handle pre-tool-use events.

        Provides relevant memories before tool execution.
        """
        tool_name = context.get("tool_name", "")
        tool_args = context.get("arguments", {})

        # Only provide hints for certain tools or contexts
        if not self._should_provide_memory_hint(tool_name, tool_args):
            return None

        # Extract context for memory search
        search_context = self._extract_search_context(tool_name, tool_args, context)

        if not search_context:
            return None

        # Get relevant memories
        memories = await self._get_relevant_memories(search_context, user_id)

        if not memories:
            return None

        return self._format_memory_hint(memories, "before using this tool")

    async def _handle_post_tool_use(self, context: dict, user_id: str) -> str | None:
        """Handle post-tool-use events.

        Provides related memories or suggestions after tool completion.
        """
        tool_name = context.get("tool_name", "")
        tool_result = context.get("result", "")

        # Analyze tool result for follow-up opportunities
        if self._indicates_problem(tool_result):
            # User encountered an issue, provide debugging memories
            memories = await self._get_relevant_memories(
                "debugging error fix", user_id, limit=3
            )
            if memories:
                return self._format_memory_hint(memories, "for troubleshooting")

        elif self._indicates_success(tool_result):
            # Tool succeeded, maybe suggest next steps
            suggestions = await self._get_contextual_suggestions(tool_name, user_id)
            if suggestions:
                return f"💡 Based on your history: {suggestions[0]}"

        return None

    async def _handle_notification(self, context: dict, user_id: str) -> str | None:
        """Handle notification events.

        Provides context when starting new conversations or sessions.
        """
        notification_type = context.get("type", "")

        if notification_type == "session_start":
            # New session starting, provide recent context
            return await self._provide_session_context(user_id)
        elif notification_type == "conversation_start":
            # New conversation, suggest continuing previous work
            return await self._suggest_conversation_continuation(user_id)

        return None

    def _should_provide_memory_hint(self, tool_name: str, tool_args: dict) -> bool:
        """Determine if we should provide memory hints for this tool use.

        Args:
            tool_name: Name of the tool being used
            tool_args: Arguments passed to the tool

        Returns:
            True if we should provide memory hints
        """
        # Check for file operations first - be selective about file types
        if tool_name.lower() in ["read", "edit", "write"]:
            file_path = tool_args.get("file_path", "")
            # Only provide hints for code-related files
            code_extensions = [
                ".js",
                ".ts",
                ".py",
                ".css",
                ".html",
                ".jsx",
                ".tsx",
                ".vue",
                ".java",
                ".cpp",
                ".c",
                ".rs",
            ]
            if any(ext in file_path for ext in code_extensions):
                return True
            # Exclude documentation and config files
            excluded_patterns = [
                "README",
                ".md",
                ".txt",
                ".json",
                ".yaml",
                ".yml",
                ".toml",
                ".ini",
            ]
            if any(pattern in file_path for pattern in excluded_patterns):
                return False
            return False

        # Check for bash/shell commands - only for problem-solving
        if tool_name.lower() == "bash":
            command = tool_args.get("command", "")
            problem_solving_keywords = [
                "debug",
                "test",
                "fix",
                "error",
                "install",
                "npm test",
                "pytest",
                "jest",
            ]
            if any(keyword in command.lower() for keyword in problem_solving_keywords):
                return True
            # Exclude basic commands
            basic_commands = [
                "ls",
                "cd",
                "pwd",
                "cat",
                "echo",
                "mkdir",
                "rm",
                "cp",
                "mv",
            ]
            if any(cmd in command.lower() for cmd in basic_commands):
                return False
            return False

        # Provide hints for other development tools
        other_dev_tools = ["grep", "glob", "python", "node", "npm", "git", "docker"]
        return bool(any(dev_tool in tool_name.lower() for dev_tool in other_dev_tools))

    def _extract_search_context(
        self, tool_name: str, tool_args: dict, context: dict
    ) -> str:
        """Extract search context from tool usage.

        Args:
            tool_name: Name of the tool
            tool_args: Tool arguments
            context: Full context

        Returns:
            Search context string
        """
        context_parts = []

        # Add tool name as context
        context_parts.append(tool_name)

        # Extract relevant arguments
        if "file_path" in tool_args:
            file_path = tool_args["file_path"]
            # Extract technology from file extension
            if ".js" in file_path or ".jsx" in file_path:
                context_parts.append("javascript react")
            elif ".ts" in file_path or ".tsx" in file_path:
                context_parts.append("typescript react")
            elif ".py" in file_path:
                context_parts.append("python")
            elif ".css" in file_path or ".scss" in file_path:
                context_parts.append("css styling")

        # Extract from command
        if "command" in tool_args:
            command = tool_args["command"].lower()
            # Look for technology keywords
            tech_keywords = ["react", "node", "python", "docker", "git", "npm", "pip"]
            for keyword in tech_keywords:
                if keyword in command:
                    context_parts.append(keyword)

        return " ".join(context_parts[:3])  # Limit context length

    async def _get_relevant_memories(
        self, search_context: str, user_id: str, limit: int = 5
    ) -> list[dict]:
        """Get memories relevant to the current context.

        Args:
            search_context: Context to search for
            user_id: User identifier
            limit: Maximum memories to return

        Returns:
            List of relevant memories
        """
        if not search_context.strip():
            return []

        try:
            memories = await self.memory_service.search_memories(
                query=search_context, user_id=user_id, limit=limit
            )

            # Filter for relevance (basic scoring)
            relevant_memories = []
            context_words = set(search_context.lower().split())

            for memory in memories:
                memory_content = memory.get("memory", "").lower()
                memory_words = set(memory_content.split())

                # Calculate simple relevance score
                overlap = len(context_words.intersection(memory_words))
                if overlap > 0:
                    memory["relevance_score"] = overlap
                    relevant_memories.append(memory)

            # Sort by relevance
            relevant_memories.sort(
                key=lambda x: x.get("relevance_score", 0), reverse=True
            )

            return relevant_memories[:3]  # Return top 3 most relevant

        except Exception as e:
            logger.error(f"Error getting relevant memories: {e}")
            return []

    def _format_memory_hint(
        self, memories: list[dict], context_suffix: str = ""
    ) -> str:
        """Format memories for proactive delivery.

        Args:
            memories: List of memory dictionaries
            context_suffix: Additional context for the hint

        Returns:
            Formatted memory hint string
        """
        if not memories:
            return ""

        if len(memories) == 1:
            memory = memories[0]
            content = memory.get("memory", "")[:100]  # Limit length
            return f"💭 Based on our previous discussion: {content}... {context_suffix}"
        else:
            # Multiple memories
            hint = f"💭 Based on our previous discussions {context_suffix}:\n"
            for i, memory in enumerate(memories[:2], 1):  # Show max 2
                content = memory.get("memory", "")[:80]
                hint += f"{i}. {content}...\n"
            return hint.strip()

    def _indicates_problem(self, tool_result: str) -> bool:
        """Check if tool result indicates a problem or error.

        Args:
            tool_result: Result from tool execution

        Returns:
            True if result indicates a problem
        """
        problem_indicators = [
            "error",
            "failed",
            "exception",
            "not found",
            "permission denied",
            "syntax error",
            "undefined",
            "null reference",
            "timeout",
            "connection refused",
            "404",
            "500",
        ]

        result_lower = tool_result.lower()
        return any(indicator in result_lower for indicator in problem_indicators)

    def _indicates_success(self, tool_result: str) -> bool:
        """Check if tool result indicates success.

        Args:
            tool_result: Result from tool execution

        Returns:
            True if result indicates success
        """
        success_indicators = [
            "success",
            "completed",
            "done",
            "created",
            "updated",
            "installed",
            "built",
            "deployed",
            "passed",
        ]

        result_lower = tool_result.lower()
        return any(indicator in result_lower for indicator in success_indicators)

    async def _get_contextual_suggestions(
        self, tool_name: str, user_id: str
    ) -> list[str]:
        """Get contextual suggestions based on recent tool usage.

        Args:
            tool_name: Name of the tool that was used
            user_id: User identifier

        Returns:
            List of suggestion strings
        """
        try:
            # Get recent memories for context
            memories = await self.memory_service.get_memories(user_id, limit=10)

            if not memories:
                return []

            # Generate suggestions based on tool and context
            context = f"after using {tool_name}"
            suggestions = await self.reflection_agent.suggest_actions(context, memories)

            return suggestions[:2]  # Return top 2 suggestions

        except Exception as e:
            logger.error(f"Error getting contextual suggestions: {e}")
            return []

    async def _provide_session_context(self, user_id: str) -> str | None:
        """Provide context for new session.

        Args:
            user_id: User identifier

        Returns:
            Session context string or None
        """
        try:
            # Get recent memories
            memories = await self.memory_service.get_memories(user_id, limit=5)

            if not memories:
                return "👋 Welcome back! No previous conversation history found."

            # Analyze recent activity
            analysis = await self.reflection_agent.analyze_patterns(memories, limit=5)
            topics = analysis.get("topics", {})

            if topics:
                top_topic = max(topics.items(), key=lambda x: x[1])[0]
                return f"👋 Welcome back! Recently you've been working on {top_topic}. Would you like to continue?"
            else:
                return "👋 Welcome back! Ready to continue where we left off?"

        except Exception as e:
            logger.error(f"Error providing session context: {e}")
            return None

    async def _suggest_conversation_continuation(self, user_id: str) -> str | None:
        """Suggest continuing previous conversation topics.

        Args:
            user_id: User identifier

        Returns:
            Continuation suggestion or None
        """
        try:
            # Get very recent memories (last conversation)
            memories = await self.memory_service.get_memories(user_id, limit=3)

            if not memories:
                return None

            # Find incomplete tasks or questions
            recent_content = " ".join([m.get("memory", "") for m in memories])

            # Look for patterns suggesting incomplete work
            if re.search(
                r"\btodo\b|\bnext\b|\bcontinue\b|\bwip\b", recent_content, re.IGNORECASE
            ):
                return "💡 It looks like you have some ongoing work. Would you like me to help you continue?"
            elif re.search(
                r"\berror\b|\bissue\b|\bproblem\b", recent_content, re.IGNORECASE
            ):
                return "🔧 I see you were working through some issues. Need help resolving them?"

            return None

        except Exception as e:
            logger.error(f"Error suggesting conversation continuation: {e}")
            return None


# Convenience functions for use in Claude Code hooks


async def handle_pre_tool_use(tool_name: str, arguments: dict, **kwargs) -> str | None:
    """Convenience function for PreToolUse hook.

    Args:
        tool_name: Name of the tool being used
        arguments: Tool arguments
        **kwargs: Additional context

    Returns:
        Memory hint or None
    """
    try:
        settings = get_settings()
        memory_service = MemoryService(settings.mem0_api_key)
        reflection_agent = ReflectionAgent(memory_service)
        handler = HookHandler(memory_service, reflection_agent)

        context = {"tool_name": tool_name, "arguments": arguments, **kwargs}

        return await handler.handle_hook_event(
            "PreToolUse", context, settings.default_user_id
        )

    except Exception as e:
        logger.error(f"Error in pre-tool-use hook: {e}")
        return None


async def handle_post_tool_use(tool_name: str, result: str, **kwargs) -> str | None:
    """Convenience function for PostToolUse hook.

    Args:
        tool_name: Name of the tool that was used
        result: Result from tool execution
        **kwargs: Additional context

    Returns:
        Follow-up suggestion or None
    """
    try:
        settings = get_settings()
        memory_service = MemoryService(settings.mem0_api_key)
        reflection_agent = ReflectionAgent(memory_service)
        handler = HookHandler(memory_service, reflection_agent)

        context = {"tool_name": tool_name, "result": result, **kwargs}

        return await handler.handle_hook_event(
            "PostToolUse", context, settings.default_user_id
        )

    except Exception as e:
        logger.error(f"Error in post-tool-use hook: {e}")
        return None

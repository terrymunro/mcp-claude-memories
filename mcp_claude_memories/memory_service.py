"""Memory service for interacting with Mem0 SaaS."""

import asyncio
import logging
from datetime import datetime

from mem0 import MemoryClient

logger = logging.getLogger(__name__)


class MemoryService:
    """Service for storing and retrieving conversation memories using Mem0."""

    def __init__(self, api_key: str):
        """Initialize the memory service with Mem0 API key."""
        if not api_key or not api_key.strip():
            raise ValueError("Mem0 API key is required")

        self.client = MemoryClient(api_key)
        self.max_retries = 3
        self.retry_delay = 1.0  # seconds

    async def _retry_on_network_error(self, operation, *args, **kwargs):
        """Retry an operation on network-related errors."""
        last_exception = None

        for attempt in range(self.max_retries):
            try:
                return operation(*args, **kwargs)
            except Exception as e:
                last_exception = e
                error_msg = str(e).lower()

                # Check if it's a retryable error
                retryable = any(
                    keyword in error_msg
                    for keyword in [
                        "timeout",
                        "connection",
                        "network",
                        "temporary",
                        "rate limit",
                        "502",
                        "503",
                        "504",
                    ]
                )

                if not retryable or attempt == self.max_retries - 1:
                    # Not retryable or final attempt
                    raise e

                # Wait before retry with exponential backoff
                wait_time = self.retry_delay * (2**attempt)
                logger.warning(
                    f"API call failed (attempt {attempt + 1}/{self.max_retries}), retrying in {wait_time}s: {e}"
                )
                await asyncio.sleep(wait_time)

        # Should not reach here, but just in case
        raise last_exception

    async def store_conversation(
        self,
        user_id: str,
        project_name: str,
        messages: list[dict],
        metadata: dict | None = None,
    ) -> str:
        """Store conversation messages in Mem0.

        Args:
            user_id: User identifier
            project_name: Name of the project/conversation context
            messages: List of message dictionaries with role and content
            metadata: Additional metadata for the memory

        Returns:
            Memory ID from Mem0
        """
        try:
            # Format messages for storage
            formatted_messages = []
            for msg in messages:
                formatted_messages.append({
                    "role": msg.get("role", "unknown"),
                    "content": msg.get("content", ""),
                })

            # Prepare metadata
            storage_metadata = {
                "project_name": project_name,
                "timestamp": datetime.utcnow().isoformat(),
                "message_count": len(messages),
                **(metadata or {}),
            }

            # Store in Mem0 with retry logic
            result = await self._retry_on_network_error(
                self.client.add,
                messages=formatted_messages,
                user_id=user_id,
                metadata=storage_metadata,
            )

            memory_id = result.get("id") if result else None
            logger.info(f"Stored conversation memory {memory_id} for user {user_id}")

            return memory_id

        except Exception as e:
            logger.error(f"Error storing conversation: {e}")
            raise

    async def search_memories(
        self, query: str, user_id: str = "default", limit: int = 10
    ) -> list[dict]:
        """Search memories using natural language query.

        Args:
            query: Natural language search query
            user_id: User identifier
            limit: Maximum number of results

        Returns:
            List of matching memories
        """
        try:
            results = await self._retry_on_network_error(
                self.client.search, query=query, user_id=user_id, limit=limit
            )

            memories = results.get("memories", []) if results else []
            logger.info(f"Found {len(memories)} memories for query: {query}")

            return memories

        except Exception as e:
            logger.error(f"Error searching memories: {e}")
            raise

    async def get_memories(
        self, user_id: str = "default", limit: int = 20
    ) -> list[dict]:
        """Get recent memories for a user.

        Args:
            user_id: User identifier
            limit: Maximum number of memories to return

        Returns:
            List of recent memories
        """
        try:
            results = await self._retry_on_network_error(
                self.client.get_all, user_id=user_id, limit=limit
            )

            memories = results.get("memories", []) if results else []
            logger.info(f"Retrieved {len(memories)} memories for user {user_id}")

            return memories

        except Exception as e:
            logger.error(f"Error getting memories: {e}")
            raise

    async def delete_memory(self, memory_id: str) -> bool:
        """Delete a specific memory by ID.

        Args:
            memory_id: Unique identifier of the memory

        Returns:
            True if deletion was successful
        """
        try:
            result = await self._retry_on_network_error(
                self.client.delete, memory_id=memory_id
            )

            success = result is not None
            if success:
                logger.info(f"Deleted memory {memory_id}")
            else:
                logger.warning(f"Failed to delete memory {memory_id}")

            return success

        except Exception as e:
            logger.error(f"Error deleting memory {memory_id}: {e}")
            raise

    def format_memory_for_display(self, memory: dict) -> str:
        """Format a memory for human-readable display.

        Args:
            memory: Memory dictionary from Mem0

        Returns:
            Formatted string representation
        """
        memory_id = memory.get("id", "unknown")
        content = memory.get("memory", "")
        metadata = memory.get("metadata", {})

        # Extract useful metadata
        project = metadata.get("project_name", "Unknown Project")
        timestamp = metadata.get("timestamp", "Unknown Time")

        # Try to parse timestamp for better formatting
        try:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            formatted_time = dt.strftime("%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            formatted_time = timestamp

        return f"[{memory_id}] {project} ({formatted_time}): {content}"

    def format_memories_list(self, memories: list[dict]) -> str:
        """Format a list of memories for display.

        Args:
            memories: List of memory dictionaries

        Returns:
            Formatted string with all memories
        """
        if not memories:
            return "No memories found."

        formatted = []
        for i, memory in enumerate(memories, 1):
            formatted.append(f"{i}. {self.format_memory_for_display(memory)}")

        return "\n".join(formatted)

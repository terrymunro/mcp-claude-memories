"""Parser for Claude conversation JSONL files."""

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class ConversationParser:
    """Parser for Claude JSONL conversation files."""

    def parse_jsonl_file(self, file_path: Path, start_line: int = 0) -> list[dict]:
        """Parse JSONL file from specific line onwards.

        Args:
            file_path: Path to the JSONL file
            start_line: Line number to start reading from (0-indexed)

        Returns:
            List of parsed JSON objects
        """
        parsed_data = []

        try:
            with open(file_path, encoding="utf-8") as f:
                for line_num, line in enumerate(f):
                    # Skip lines before start_line
                    if line_num < start_line:
                        continue

                    line = line.strip()
                    if not line:
                        continue

                    try:
                        data = json.loads(line)
                        data["_line_number"] = line_num
                        parsed_data.append(data)
                    except json.JSONDecodeError as e:
                        logger.warning(
                            f"Invalid JSON at line {line_num} in {file_path}: {e}"
                        )
                        continue

        except FileNotFoundError:
            logger.error(f"File not found: {file_path}")
            return []
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return []

        logger.info(
            f"Parsed {len(parsed_data)} lines from {file_path} (starting from line {start_line})"
        )
        return parsed_data

    def extract_messages(self, jsonl_data: list[dict]) -> list[dict]:
        """Extract user/assistant messages from JSONL data.

        Args:
            jsonl_data: List of parsed JSON objects from JSONL file

        Returns:
            List of message dictionaries with role and content
        """
        messages = []

        for entry in jsonl_data:
            # Skip non-message entries
            if not self._is_message_entry(entry):
                continue

            # Get role from either 'type' (Claude format) or 'role' (legacy format)
            role = entry.get("type") or entry.get("role")
            content = self._extract_content(entry)

            if role and content:
                messages.append({
                    "role": role,
                    "content": content,
                    "timestamp": entry.get("timestamp"),
                    "line_number": entry.get("_line_number"),
                })

        logger.info(f"Extracted {len(messages)} messages from JSONL data")
        return messages

    def extract_metadata(self, file_path: Path, jsonl_data: list[dict]) -> dict:
        """Extract metadata from file path and JSONL data.

        Args:
            file_path: Path to the conversation file
            jsonl_data: Parsed JSONL data

        Returns:
            Dictionary with metadata
        """
        metadata = {
            "file_path": str(file_path),
            "file_name": file_path.name,
            "project_name": self._extract_project_name(file_path),
            "conversation_id": self._extract_conversation_id(file_path),
            "total_lines": len(jsonl_data),
            "parsed_at": datetime.utcnow().isoformat(),
        }

        # Extract conversation-level metadata if available
        if jsonl_data:
            first_entry = jsonl_data[0]
            last_entry = jsonl_data[-1]

            metadata.update({
                "first_timestamp": first_entry.get("timestamp"),
                "last_timestamp": last_entry.get("timestamp"),
                "first_line": first_entry.get("_line_number", 0),
                "last_line": last_entry.get("_line_number", 0),
            })

        return metadata

    def _is_message_entry(self, entry: dict) -> bool:
        """Check if entry is a message (user or assistant).

        Args:
            entry: JSON entry from JSONL file

        Returns:
            True if entry contains a message
        """
        # Check both 'type' (actual Claude format) and 'role' (for backwards compatibility)
        message_type = entry.get("type") or entry.get("role")
        content = entry.get("content")

        # Must have both type/role and content
        if not message_type or not content:
            return False

        # Only process user and assistant messages for now
        return message_type in ["user", "assistant"]

    def _extract_content(self, entry: dict) -> str | None:
        """Extract text content from message entry.

        Args:
            entry: Message entry from JSONL

        Returns:
            Text content or None if not extractable
        """
        content = entry.get("content")

        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            # Handle content that's a list of objects (e.g., text blocks)
            text_parts = []
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
                    # For now, ignore tool calls, images, etc.
                elif isinstance(item, str):
                    text_parts.append(item)

            return "\n".join(text_parts) if text_parts else None

        return None

    def _extract_project_name(self, file_path: Path) -> str:
        """Extract project name from file path.

        Args:
            file_path: Path to conversation file

        Returns:
            Project name or 'unknown'
        """
        # Path structure: ~/.config/claude/projects/{project_name}/conversation*.jsonl
        try:
            parts = file_path.parts
            projects_index = next(
                i for i, part in enumerate(parts) if part == "projects"
            )
            if projects_index + 1 < len(parts):
                return parts[projects_index + 1]
        except (StopIteration, IndexError):
            pass

        return "unknown"

    def _extract_conversation_id(self, file_path: Path) -> str:
        """Extract conversation ID from file name.

        Args:
            file_path: Path to conversation file

        Returns:
            Conversation ID from filename
        """
        # Extract ID from filename like "conversation_abc123.jsonl"
        stem = file_path.stem
        if "_" in stem:
            return stem.split("_", 1)[1]

        return stem

    def extract_conversation_messages(self, jsonl_data: list[dict]) -> list[dict]:
        """Extract conversation messages in a format suitable for memory storage.

        Args:
            jsonl_data: List of parsed JSON objects from JSONL file

        Returns:
            List of message dictionaries with role and content for memory service
        """
        try:
            messages = self.extract_messages(jsonl_data)

            # Convert to memory service format
            formatted_messages = []
            for msg in messages:
                role = msg.get("role", "")
                content = msg.get("content", "")

                # Map Claude roles to standard format
                if role == "user":
                    formatted_role = "human"
                elif role == "assistant":
                    formatted_role = "assistant"
                else:
                    formatted_role = role

                if content and content.strip():
                    formatted_messages.append({
                        "role": formatted_role,
                        "content": content.strip(),
                    })

            logger.info(
                f"Formatted {len(formatted_messages)} messages for memory storage"
            )
            return formatted_messages

        except Exception as e:
            logger.error(f"Error extracting conversation messages: {e}")
            return []

    def get_file_line_count(self, file_path: Path) -> int:
        """Get total number of lines in a file.

        Args:
            file_path: Path to file

        Returns:
            Number of lines in file
        """
        try:
            with open(file_path, encoding="utf-8") as f:
                return sum(1 for _ in f)
        except (FileNotFoundError, PermissionError) as e:
            logger.warning(f"Cannot access file {file_path}: {e}")
            return 0
        except Exception as e:
            logger.error(f"Error counting lines in {file_path}: {e}")
            return 0

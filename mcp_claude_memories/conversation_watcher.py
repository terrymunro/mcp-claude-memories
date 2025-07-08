"""File watcher for monitoring Claude conversation files."""

import asyncio
import logging
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .conversation_parser import ConversationParser
from .memory_service import MemoryService

logger = logging.getLogger(__name__)


class ConversationFileHandler(FileSystemEventHandler):
    """Handler for conversation file system events."""

    def __init__(self, watcher: "ConversationWatcher"):
        """Initialize handler with watcher reference."""
        self.watcher = watcher
        self._last_modified: dict[str, float] = {}
        self._debounce_delay = 2.0  # Wait 2 seconds after last modification

    def on_modified(self, event):
        """Handle file modification events."""
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        # Check if it matches our patterns
        if not self._matches_patterns(file_path):
            return

        # Debounce: only process if file hasn't been modified recently
        current_time = time.time()
        last_mod = self._last_modified.get(str(file_path), 0)

        if current_time - last_mod < self._debounce_delay:
            return

        self._last_modified[str(file_path)] = current_time

        # Schedule processing
        asyncio.create_task(self.watcher._process_file_changes(file_path))

    def _matches_patterns(self, file_path: Path) -> bool:
        """Check if file matches our watch patterns."""
        patterns = self.watcher.watch_patterns

        return any(file_path.match(pattern) for pattern in patterns)


class ConversationWatcher:
    """Monitors Claude conversation files and stores them in memory."""

    def __init__(
        self,
        memory_service: MemoryService,
        claude_config_dir: Path,
        watch_patterns: list[str],
        default_user_id: str = "default",
    ):
        """Initialize the conversation watcher.

        Args:
            memory_service: Service for storing memories
            claude_config_dir: Path to Claude configuration directory
            watch_patterns: File patterns to watch (e.g., ['conversation*.jsonl'])
            default_user_id: Default user ID for memory storage
        """
        self.memory_service = memory_service
        self.claude_config_dir = claude_config_dir
        self.watch_patterns = watch_patterns
        self.default_user_id = default_user_id

        self.parser = ConversationParser()
        self.observer: Observer | None = None

        # Track last processed line for each file
        self._file_positions: dict[str, int] = {}

        # Track which directories we're watching
        self._watched_dirs: set[Path] = set()

    async def start_watching(self):
        """Start monitoring conversation files."""
        logger.info("Starting conversation file watcher")

        # Get directories to watch
        watch_dirs = self._get_watch_directories()

        if not watch_dirs:
            logger.warning("No project directories found to watch")
            return

        # Set up file system observer
        self.observer = Observer()
        handler = ConversationFileHandler(self)

        # Watch each project directory
        for watch_dir in watch_dirs:
            if watch_dir.exists():
                self.observer.schedule(handler, str(watch_dir), recursive=False)
                self._watched_dirs.add(watch_dir)
                logger.info(f"Watching directory: {watch_dir}")
            else:
                logger.warning(f"Directory does not exist: {watch_dir}")

        # Start observer
        self.observer.start()

        # Process existing files on startup
        await self._process_existing_files()

        logger.info("Conversation watcher started successfully")

    def stop_watching(self):
        """Stop monitoring conversation files."""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            logger.info("Conversation watcher stopped")

    async def _process_existing_files(self):
        """Process existing conversation files on startup."""
        logger.info("Processing existing conversation files")

        for watch_dir in self._watched_dirs:
            for pattern in self.watch_patterns:
                for file_path in watch_dir.glob(pattern):
                    if file_path.is_file():
                        await self._process_file_changes(file_path, is_startup=True)

    async def _process_file_changes(self, file_path: Path, is_startup: bool = False):
        """Process changes in a conversation file.

        Args:
            file_path: Path to the changed file
            is_startup: Whether this is being called during startup
        """
        try:
            file_key = str(file_path)

            # Get current file line count
            current_lines = self.parser.get_file_line_count(file_path)
            last_processed = self._file_positions.get(file_key, 0)

            # Skip if no new content
            if current_lines <= last_processed:
                return

            # Only process new lines
            start_line = last_processed if not is_startup else 0

            logger.info(f"Processing {file_path} from line {start_line}")

            # Parse new content
            jsonl_data = self.parser.parse_jsonl_file(file_path, start_line)

            if not jsonl_data:
                return

            # Extract messages
            messages = self.parser.extract_conversation_messages(jsonl_data)

            if not messages:
                logger.debug(f"No new messages found in {file_path}")
                self._file_positions[file_key] = current_lines
                return

            # Extract metadata
            metadata = self.parser.extract_metadata(file_path, jsonl_data)
            project_name = metadata.get("project_name", "unknown")

            # Store in memory service
            memory_id = await self.memory_service.store_conversation(
                user_id=self.default_user_id,
                project_name=project_name,
                messages=messages,
                metadata=metadata,
            )

            # Update position tracking
            self._file_positions[file_key] = current_lines

            logger.info(
                f"Stored {len(messages)} messages from {file_path} "
                f"(memory: {memory_id})"
            )

        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")

    def _get_watch_directories(self) -> list[Path]:
        """Get list of project directories to watch."""
        projects_dir = self.claude_config_dir / "projects"

        if not projects_dir.exists():
            logger.warning(f"Projects directory not found: {projects_dir}")
            return []

        watch_dirs = []
        for project_dir in projects_dir.iterdir():
            if project_dir.is_dir():
                watch_dirs.append(project_dir)

        logger.info(f"Found {len(watch_dirs)} project directories to watch")
        return watch_dirs

    def get_processing_status(self) -> dict:
        """Get current processing status for debugging."""
        return {
            "watched_directories": [str(d) for d in self._watched_dirs],
            "file_positions": self._file_positions.copy(),
            "watch_patterns": self.watch_patterns,
            "is_watching": self.observer is not None and self.observer.is_alive(),
        }


async def run_watcher(
    memory_service: MemoryService,
    claude_config_dir: Path,
    watch_patterns: list[str],
    default_user_id: str = "default",
):
    """Run the conversation watcher indefinitely.

    Args:
        memory_service: Service for storing memories
        claude_config_dir: Path to Claude configuration directory
        watch_patterns: File patterns to watch
        default_user_id: Default user ID for memory storage
    """
    watcher = ConversationWatcher(
        memory_service=memory_service,
        claude_config_dir=claude_config_dir,
        watch_patterns=watch_patterns,
        default_user_id=default_user_id,
    )

    try:
        await watcher.start_watching()

        # Keep running until interrupted
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        watcher.stop_watching()

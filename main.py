"""Main entry point for running the conversation watcher as a background service."""

import asyncio
import logging
import signal
import sys

from mcp_claude_memories.config import get_settings
from mcp_claude_memories.conversation_watcher import run_watcher
from mcp_claude_memories.memory_service import MemoryService


def setup_logging(debug: bool = False):
    """Setup basic logging configuration."""
    level = logging.DEBUG if debug else logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("claude_memories_watcher.log"),
        ],
    )

    # Reduce noise from external libraries
    logging.getLogger("watchdog").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown."""

    def signal_handler(signum, frame):
        logging.info(f"Received signal {signum}")
        # This will cause the asyncio loop to exit cleanly
        raise KeyboardInterrupt()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


async def main():
    """Main async entry point."""
    try:
        # Load configuration
        settings = get_settings()

        # Setup logging
        setup_logging(settings.debug)
        logger = logging.getLogger(__name__)

        logger.info("Starting Claude Memories Watcher")
        logger.info(f"Claude config dir: {settings.claude_config_dir}")
        logger.info(f"Watch patterns: {settings.watch_patterns}")
        logger.info(f"Default user ID: {settings.default_user_id}")

        # Initialize memory service
        memory_service = MemoryService(settings.mem0_api_key)

        # Run watcher
        await run_watcher(
            memory_service=memory_service,
            claude_config_dir=settings.claude_config_dir,
            watch_patterns=settings.watch_patterns,
            default_user_id=settings.default_user_id,
        )

    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    # Setup signal handlers
    setup_signal_handlers()

    # Run main async function
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

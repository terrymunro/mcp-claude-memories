"""Tests for configuration module."""

import pytest

from mcp_claude_memories.config import Settings, get_settings


def test_settings_with_defaults():
    """Test settings with default values."""
    settings = Settings(mem0_api_key="test_key_long_enough")

    assert settings.mem0_api_key == "test_key_long_enough"
    assert settings.default_user_id == "default_user"
    assert settings.debug is False
    assert settings.watch_patterns == ["conversation*.jsonl"]


def test_settings_with_env_vars(tmp_path):
    """Test settings loaded from environment variables."""
    env_vars = {
        "MEM0_API_KEY": "env_test_key_long_enough",
        "DEFAULT_USER_ID": "test_user",
        "DEBUG": "true",
        "CLAUDE_CONFIG_DIR": str(tmp_path),
    }

    with pytest.MonkeyPatch.context() as patch:
        for key, value in env_vars.items():
            patch.setenv(key, value)

        settings = Settings()

        assert settings.mem0_api_key == "env_test_key_long_enough"
        assert settings.default_user_id == "test_user"
        assert settings.debug is True
        assert settings.claude_config_dir == tmp_path


def test_get_watch_directories(tmp_path):
    """Test getting watch directories."""
    projects_dir = tmp_path / "projects"
    projects_dir.mkdir()

    # Create test project directories
    (projects_dir / "project1").mkdir()
    (projects_dir / "project2").mkdir()
    (projects_dir / "file.txt").touch()  # Should be ignored

    settings = Settings(mem0_api_key="test_key_long_enough", claude_config_dir=tmp_path)

    watch_dirs = settings.get_watch_directories()

    assert len(watch_dirs) == 2
    assert projects_dir / "project1" in watch_dirs
    assert projects_dir / "project2" in watch_dirs


def test_get_watch_directories_no_projects(tmp_path):
    """Test getting watch directories when projects dir doesn't exist."""
    settings = Settings(mem0_api_key="test_key_long_enough", claude_config_dir=tmp_path)

    watch_dirs = settings.get_watch_directories()

    assert watch_dirs == []


def test_get_settings():
    """Test get_settings function."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("MEM0_API_KEY", "function_test_key_long_enough")

        settings = get_settings()

        assert isinstance(settings, Settings)
        assert settings.mem0_api_key == "function_test_key_long_enough"

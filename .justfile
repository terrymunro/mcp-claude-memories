# Display recipes when `just` is run without a target
[private]
default:
    @just --list

# MCP server
run *args:
    @echo "▶️  Starting MCP server"
    uv run python -m mcp_mitm_mem0.mcp_server {{args}}

# MITM proxy with memory addon
proxy *args:
    @echo "🔄 Starting MITM proxy with memory addon"
    mitmdump -s memory_addon.py {{args}}

# Pytest with coverage flags already in pytest.ini; forward any extra args
test *args:
    @echo "🧪 Running tests"
    uv run pytest {{args}}

# Ruff format + lint + (basic) type-checking rules
lint:
    @echo "🎨 Ruff format"
    uv run ruff format .
    @echo "🔎 Ruff lint --fix"
    uv run ruff check --fix .
    @echo "✅ Ruff final pass"
    uv run ruff check .

# (Optional but handy) install all dependency groups
install:
    uv sync --all-groups

# Clean all generated files and directories
clean:
    @echo "🧹 Cleaning Python cache files"
    @find . -type d -name "__pycache__" -or -name ".ruff_cache" -not -path "./.venv/*" -exec rm -rf {} + 2>/dev/null || true
    @find . -name "*.pyc" -not -path "./.venv/*" -delete 2>/dev/null || true
    @find . -name "*.pyo" -not -path "./.venv/*" -delete 2>/dev/null || true
    @echo "🧪 Cleaning test artifacts"
    @rm -rf .pytest_cache .coverage htmlcov coverage.xml
    @echo "📦 Cleaning build artifacts"
    @rm -rf build dist *.egg-info
    @echo "🗑️  Cleaning temporary files"
    @find . -name "*.log" -not -path "./.venv/*" -delete 2>/dev/null || true
    @find . -name "*.tmp" -not -path "./.venv/*" -delete 2>/dev/null || true
    @find . -name "*.temp" -not -path "./.venv/*" -delete 2>/dev/null || true
    @find . -name ".DS_Store" -delete 2>/dev/null || true
    @find . -name "*.swp" -delete 2>/dev/null || true
    @find . -name "*.swo" -delete 2>/dev/null || true
    @echo "✨ Clean complete"

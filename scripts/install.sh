#!/bin/bash
# memos-graph Installer
# Usage: bash scripts/install.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "========================================"
echo "  memos-graph v0.1.0 Installer"
echo "========================================"
echo ""

# Check prerequisites
echo "Checking prerequisites..."

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3.11+ is required"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo "  ✓ Python $PYTHON_VERSION"

# Check uv
if ! command -v uv &> /dev/null; then
    echo "  Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi
echo "  ✓ uv installed"

# Check PostgreSQL
if ! command -v psql &> /dev/null; then
    echo "  Warning: PostgreSQL not found. Please install PostgreSQL 15+"
    echo "  Debian/Ubuntu: sudo apt install postgresql-15 postgresql-server-dev-15"
    echo "  macOS: brew install postgresql@15"
fi
echo "  ✓ PostgreSQL check complete"

# Install the package
echo ""
echo "Installing memos-graph..."
cd "$PROJECT_ROOT"
uv pip install -e ".[dev]"

# Create config directory
echo ""
echo "Creating configuration..."
mkdir -p ~/.config/memos-graph

# Generate config if not exists
if [ ! -f ~/.config/memos-graph/config.yaml ]; then
    cat > ~/.config/memos-graph/config.yaml << 'EOF'
# memos-graph configuration

server:
  host: 127.0.0.1
  port: 8765

database:
  url: postgresql+asyncpg://memos:memos@localhost:5432/memos
  pool_size: 10
  pool_recycle: 3600

embedding:
  provider: ollama
  model: nomic-embed-text
  dimension: 768
  base_url: http://localhost:11434
  cache_db: ~/.local/share/memos-graph/embeddings.db
  timeout_seconds: 30

llm:
  base_url: https://maas-coding-api.cn-huabei-1.xf-yun.com/v1
  api_key: ${ANTHROPIC_API_KEY}
  model: astron-code-latest
  timeout_seconds: 60

viewer:
  enabled: true
  host: 127.0.0.1
  port: 8080

logging:
  level: INFO
  format: json
  file: ~/.local/share/memos-graph/logs/daemon.log
  rotation: "10 MB"
EOF
    echo "  ✓ Config created at ~/.config/memos-graph/config.yaml"
else
    echo "  ✓ Config already exists"
fi

# Create data directories
mkdir -p ~/.local/share/memos-graph/{logs,packs,backups}
echo "  ✓ Data directories created"

# Run migrations
echo ""
echo "Running database migrations..."
memos-graph migrate || echo "  Warning: Migrations failed. Run manually after setting up PostgreSQL."

echo ""
echo "========================================"
echo "  Installation Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "  1. Ensure PostgreSQL 15+ is running"
echo "  2. Ensure Ollama is running (ollama serve)"
echo "  3. Run: memos-graph doctor"
echo "  4. Run: memos-graph serve --port 8765"
echo "  5. Run: memos-graph viewer --port 8080"
echo ""
echo "To install Nako pack:"
echo "  memos-graph pack install $PROJECT_ROOT/packs/nako"
echo ""

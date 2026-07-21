#!/bin/bash
# =============================================================================
# setup.sh — One-time project setup script
# Run from the project root: bash scripts/setup.sh
# =============================================================================
set -e

# Make this script itself executable (idempotent)
chmod +x "$(readlink -f "$0")" 2>/dev/null || chmod +x "$0"

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
VENV_DIR="$PROJECT_ROOT/.venv"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
info()  { echo "[INFO]  $*"; }
warn()  { echo "[WARN]  $*" >&2; }
error() { echo "[ERROR] $*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# 1. Check Python 3.11+
# ---------------------------------------------------------------------------
info "Checking Python version …"
PYTHON=$(command -v python3.11 || command -v python3.12 || command -v python3 || true)

if [ -z "$PYTHON" ]; then
  error "Python 3 not found. Install Python 3.11 or newer."
fi

PY_MAJOR=$("$PYTHON" -c "import sys; print(sys.version_info.major)")
PY_MINOR=$("$PYTHON" -c "import sys; print(sys.version_info.minor)")

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]; }; then
  error "Python 3.11+ is required. Found $("$PYTHON" --version). Please upgrade."
fi

info "Found $("$PYTHON" --version)"

# ---------------------------------------------------------------------------
# 2. Check Node.js 20+
# ---------------------------------------------------------------------------
info "Checking Node.js version …"
if ! command -v node >/dev/null 2>&1; then
  error "Node.js not found. Install Node.js 20 or newer (https://nodejs.org)."
fi

NODE_MAJOR=$(node -e "process.stdout.write(process.versions.node.split('.')[0])")
if [ "$NODE_MAJOR" -lt 20 ]; then
  error "Node.js 20+ is required. Found $(node --version). Please upgrade."
fi

info "Found Node.js $(node --version)"

# Check npm as well
if ! command -v npm >/dev/null 2>&1; then
  error "npm not found. It should ship with Node.js — please reinstall Node."
fi
info "Found npm $(npm --version)"

# ---------------------------------------------------------------------------
# 3. Create Python virtual environment
# ---------------------------------------------------------------------------
if [ -d "$VENV_DIR" ]; then
  info "Virtual environment already exists at $VENV_DIR — skipping creation."
else
  info "Creating Python virtual environment at $VENV_DIR …"
  "$PYTHON" -m venv "$VENV_DIR"
fi

# Activate venv for the rest of this script
# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"
info "Virtual environment activated."

# Upgrade pip quietly
pip install --upgrade pip --quiet

# ---------------------------------------------------------------------------
# 4. Install backend dependencies
# ---------------------------------------------------------------------------
if [ -f "$BACKEND_DIR/requirements.txt" ]; then
  info "Installing backend Python dependencies …"
  pip install -r "$BACKEND_DIR/requirements.txt"
else
  warn "No requirements.txt found in $BACKEND_DIR — skipping."
fi

# ---------------------------------------------------------------------------
# 5. Install frontend dependencies
# ---------------------------------------------------------------------------
if [ -f "$FRONTEND_DIR/package.json" ]; then
  info "Installing frontend Node.js dependencies …"
  (cd "$FRONTEND_DIR" && npm install)
else
  warn "No package.json found in $FRONTEND_DIR — skipping."
fi

# ---------------------------------------------------------------------------
# 6. Copy .env.example → .env if .env doesn't exist
# ---------------------------------------------------------------------------
ENV_EXAMPLE="$PROJECT_ROOT/.env.example"
ENV_FILE="$PROJECT_ROOT/.env"

if [ -f "$ENV_FILE" ]; then
  info ".env already exists — not overwriting."
else
  if [ -f "$ENV_EXAMPLE" ]; then
    cp "$ENV_EXAMPLE" "$ENV_FILE"
    info "Created .env from .env.example."
    warn "Remember to set ANTHROPIC_API_KEY in .env before starting the app."
  else
    warn ".env.example not found — please create .env manually."
  fi
fi

# ---------------------------------------------------------------------------
# 7. Done — print next steps
# ---------------------------------------------------------------------------
cat <<'EOF'

============================================================
  Setup complete!
============================================================

Next steps:

  1. Edit .env and set your ANTHROPIC_API_KEY (and any other
     values you'd like to override).

  2. Make sure Docker is running, then start the dev stack:

       bash scripts/start_dev.sh

  3. (Optional) Seed initial data after the stack is up:

       source .venv/bin/activate
       cd backend
       python ../scripts/seed_data.py

  4. Run the test suite:

       source .venv/bin/activate
       cd backend
       python -m pytest ../tests/ -v

Services once running:
  - Backend API : http://localhost:8000
  - API docs    : http://localhost:8000/docs
  - Frontend    : http://localhost:3000
  - Elasticsearch: http://localhost:9200
  - Qdrant      : http://localhost:6333
  - Redis       : redis://localhost:6379

============================================================
EOF

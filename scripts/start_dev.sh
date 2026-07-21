#!/bin/bash
# =============================================================================
# start_dev.sh — Start the full development stack
# Run from the project root: bash scripts/start_dev.sh
# =============================================================================
set -e

chmod +x "$(readlink -f "$0")" 2>/dev/null || chmod +x "$0"

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
VENV_DIR="$PROJECT_ROOT/.venv"

# PIDs we'll track so SIGINT can stop them cleanly
BACKEND_PID=""
FRONTEND_PID=""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
info()  { echo "[INFO]  $*"; }
warn()  { echo "[WARN]  $*" >&2; }
error() { echo "[ERROR] $*" >&2; exit 1; }

wait_for_url() {
  local url="$1"
  local label="$2"
  local max_retries="${3:-30}"
  local retry=0

  info "Waiting for $label to be ready at $url …"
  until curl -sf "$url" >/dev/null 2>&1; do
    retry=$((retry + 1))
    if [ "$retry" -ge "$max_retries" ]; then
      error "$label did not become healthy after ${max_retries} retries."
    fi
    echo -n "."
    sleep 3
  done
  echo ""
  info "$label is ready."
}

# ---------------------------------------------------------------------------
# Trap — stop background processes on Ctrl-C / exit
# ---------------------------------------------------------------------------
cleanup() {
  echo ""
  info "Shutting down dev stack …"

  if [ -n "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    info "Stopping backend (PID $BACKEND_PID) …"
    kill "$BACKEND_PID"
  fi

  if [ -n "$FRONTEND_PID" ] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    info "Stopping frontend (PID $FRONTEND_PID) …"
    kill "$FRONTEND_PID"
  fi

  info "Stopping Docker Compose services …"
  (cd "$PROJECT_ROOT" && docker compose down) 2>/dev/null || true

  info "All services stopped."
}

trap cleanup INT TERM EXIT

# ---------------------------------------------------------------------------
# Preflight checks
# ---------------------------------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
  error "Docker not found. Install Docker Desktop: https://www.docker.com/products/docker-desktop/"
fi

if ! docker info >/dev/null 2>&1; then
  error "Docker daemon is not running. Please start Docker Desktop first."
fi

if [ ! -f "$PROJECT_ROOT/.env" ]; then
  warn ".env not found. Run 'bash scripts/setup.sh' first, or copy .env.example to .env."
fi

# ---------------------------------------------------------------------------
# 1. Start Docker Compose services in the background
# ---------------------------------------------------------------------------
info "Starting Docker Compose services (Elasticsearch, Qdrant, Redis) …"
(cd "$PROJECT_ROOT" && docker compose up -d)

# ---------------------------------------------------------------------------
# 2. Wait for Elasticsearch and Qdrant to be healthy
# ---------------------------------------------------------------------------
wait_for_url "http://localhost:9200" "Elasticsearch" 40
wait_for_url "http://localhost:6333/healthz" "Qdrant" 20

# ---------------------------------------------------------------------------
# 3. Activate Python venv and start backend with uvicorn --reload
# ---------------------------------------------------------------------------
if [ ! -d "$VENV_DIR" ]; then
  error "Virtual environment not found at $VENV_DIR. Run 'bash scripts/setup.sh' first."
fi

info "Starting backend API server (uvicorn --reload) …"
(
  # shellcheck source=/dev/null
  source "$VENV_DIR/bin/activate"
  cd "$BACKEND_DIR"
  uvicorn main:app --host 0.0.0.0 --port 8000 --reload \
    >> "$PROJECT_ROOT/logs/backend.log" 2>&1
) &
BACKEND_PID=$!
info "Backend started (PID $BACKEND_PID). Logs: logs/backend.log"

# Give uvicorn a moment to fail-fast if there's an import error
sleep 2
if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
  error "Backend process exited immediately. Check logs/backend.log for errors."
fi

# ---------------------------------------------------------------------------
# 4. Start frontend with npm run dev
# ---------------------------------------------------------------------------
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  warn "Frontend node_modules not found. Run 'bash scripts/setup.sh' first."
else
  info "Starting frontend (npm run dev) …"
  mkdir -p "$PROJECT_ROOT/logs"
  (
    cd "$FRONTEND_DIR"
    npm run dev >> "$PROJECT_ROOT/logs/frontend.log" 2>&1
  ) &
  FRONTEND_PID=$!
  info "Frontend started (PID $FRONTEND_PID). Logs: logs/frontend.log"
fi

# ---------------------------------------------------------------------------
# 5. Print service URLs
# ---------------------------------------------------------------------------
mkdir -p "$PROJECT_ROOT/logs"

cat <<EOF

============================================================
  Dev stack is up!
============================================================

  Backend API    : http://localhost:8000
  API docs       : http://localhost:8000/docs
  Frontend       : http://localhost:3000
  Elasticsearch  : http://localhost:9200
  Qdrant HTTP    : http://localhost:6333
  Qdrant gRPC    : localhost:6334
  Redis          : redis://localhost:6379

  Logs:
    Backend  → logs/backend.log
    Frontend → logs/frontend.log

Press Ctrl-C to stop all services.
============================================================

EOF

# Wait forever (until SIGINT)
wait

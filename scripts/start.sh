#!/bin/bash
# Start all services locally (without Docker)
# Requires: Python 3.12+ (conda env "mcp-auth"), Node.js 18+, Ollama running

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PYTHON="${PYTHON:-python}"

cd "$PROJECT_DIR"

# Check .env exists
if [ ! -f .env ]; then
    echo "ERROR: .env file not found. Copy .env.example and configure it:"
    echo "  cp .env.example .env"
    exit 1
fi

# Check .secrets
if [ ! -f .secrets/firebase-service-account.json ]; then
    echo "ERROR: .secrets/firebase-service-account.json not found."
    echo "  Place your Firebase service account JSON there."
    exit 1
fi

echo "Starting MCP Auth Demo..."
echo "  Project: $PROJECT_DIR"
echo "  Python:  $($PYTHON --version)"
echo ""

# Start MCP server
echo "[1/3] Starting MCP server on :8001..."
PYTHONPATH=. $PYTHON -m uvicorn run_mcp_server:app --host 0.0.0.0 --port 8001 &
MCP_PID=$!
sleep 3

# Start Agent API
echo "[2/3] Starting Agent API on :8000..."
PYTHONPATH=. $PYTHON -m uvicorn run_agent_api:app --host 0.0.0.0 --port 8000 &
AGENT_PID=$!
sleep 3

# Start Frontend
echo "[3/3] Starting Frontend on :5173..."
cd frontend && npx vite --host &
FRONTEND_PID=$!
cd "$PROJECT_DIR"

echo ""
echo "All services started:"
echo "  Frontend:   http://localhost:5173"
echo "  Agent API:  http://localhost:8000"
echo "  MCP Server: http://localhost:8001"
echo ""
echo "Press Ctrl+C to stop all services."

# Trap Ctrl+C and kill all background processes
trap "echo 'Stopping...'; kill $MCP_PID $AGENT_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM

# Wait for any process to exit
wait

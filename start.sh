#!/bin/bash
# TFT Coach - Single command launcher
# Starts both backend servers and frontend UI

set -e

echo "========================================"
echo "  TFT Coach - Starting All Services"
echo "========================================"

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if node_modules exists in frontend
if [ ! -d "app/frontend/node_modules" ]; then
    echo "[Setup] Installing frontend dependencies..."
    cd app/frontend && npm install && cd ../..
fi

# Start all services using concurrently from frontend
echo ""
echo "[Starting] API Server (port 8000)"
echo "[Starting] WebSocket Server (port 8765)"
echo "[Starting] Frontend UI (port 5173)"
echo ""
echo "Open http://localhost:5173 in your browser"
echo "Press Ctrl+C to stop all services"
echo ""

cd app/frontend && npm run dev:full

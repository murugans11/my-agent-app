#!/bin/bash
set -e

echo "🚀 Starting RAG·MCP Web App..."
echo "📡 MCP Server will be spawned automatically by the Host"
echo "🌐 Opening at http://localhost:8000"

# Ensure we're in the project root
cd "$(dirname "$0")"

# Load .env if present
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

# Verify API key
if [ -z "$ANTHROPIC_API_KEY" ] || [ "$ANTHROPIC_API_KEY" = "your_key_here" ]; then
  echo "⚠️  ANTHROPIC_API_KEY not set. Copy .env.example to .env and add your key."
  exit 1
fi

cd host && ../.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload

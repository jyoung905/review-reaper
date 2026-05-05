#!/bin/bash
# Review Reaper — Quick Start
# Source the venv, check for .env, and start the API server

cd "$(dirname "$0")"

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
fi

# Check for .env
if [ ! -f ".env" ]; then
    echo ""
    echo "⚠️  No .env file found. Creating from template..."
    cp .env.template .env
    echo ""
    echo "✏️  Edit .env to add your API keys (optional for dry-run):"
    echo "   OPENAI_API_KEY=your_key"
    echo "   ADMIN_PASSWORD=your_password"
    echo ""
    echo "Then run this script again."
    exit 1
fi

echo ""
echo "☠️  Review Reaper"
echo "================"
echo ""
echo "Available commands:"
echo ""
echo "  Start server:     python api/server.py [--port 8081]"
echo "  Full pipeline:    python -m src.pipeline --step all --place-id <place_id>"
echo "  Run audit:        python -m src.pipeline --step audit --place-id <place_id>"
echo "  Init database:    python -m src.pipeline --init-db"
echo "  Show dashboard:   python -m src.pipeline"
echo ""

# Start the server by default
exec python api/server.py "$@"

#!/bin/bash

# Start Next.js Frontend
# Usage:
#   ./start_ui.sh            — development mode (default)
#   ./start_ui.sh prod       — production mode (build + start)

set -e

MODE="${1:-dev}"

echo "=========================================="
echo "  Starting Nestle UI Frontend"
echo "  Mode: $MODE"
echo "=========================================="
echo ""

# Get the project root directory (parent of scripts directory)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Change to project root
cd "$PROJECT_ROOT"
echo "Working directory: $PROJECT_ROOT"

# Activate conda environment for Python dependencies (if any)
echo "Activating conda environment: ocr..."
eval "$(conda shell.bash hook)"
conda activate ocr 2>/dev/null || echo "Warning: Could not activate conda environment 'ocr'"

# Navigate to UI directory
cd src/ui

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "Node modules not found. Installing dependencies..."
    echo ""

    if command -v pnpm &> /dev/null; then
        echo "Using pnpm..."
        pnpm install
    elif command -v npm &> /dev/null; then
        echo "Using npm with --legacy-peer-deps..."
        npm install --legacy-peer-deps
    else
        echo "Error: Neither pnpm nor npm found. Please install Node.js and npm."
        exit 1
    fi
fi

# Check if .env.local exists
if [ ! -f ".env.local" ]; then
    echo "Warning: .env.local not found"
    echo "Creating default .env.local file..."

    BACKEND_URL=${API_BACKEND_URL:-"http://localhost:8000"}

    cat > .env.local << EOF
# Server-side only: backend URL used by the Next.js proxy rewrite.
# The browser never sees this value — it uses relative paths (/api/v1/...).
API_BACKEND_URL=$BACKEND_URL

NEXT_PUBLIC_API_KEY=dev-key-12345
EOF
    echo "Created .env.local with API_BACKEND_URL: $BACKEND_URL"
fi

echo ""

HOSTNAME_FLAG="--hostname 0.0.0.0"
PORT_FLAG="--port 3000"

if [ "$MODE" = "prod" ]; then
    echo "Building production bundle..."
    echo ""

    if command -v pnpm &> /dev/null; then
        pnpm build
    else
        npm run build
    fi

    echo ""
    echo "Starting Next.js production server..."
    echo "UI will be available at: http://54.236.135.105:3000"
    echo ""
    echo "Press Ctrl+C to stop the server"
    echo ""

    if command -v pnpm &> /dev/null; then
        pnpm start $HOSTNAME_FLAG $PORT_FLAG
    else
        npx next start $HOSTNAME_FLAG $PORT_FLAG
    fi
else
    echo "Starting Next.js development server..."
    echo "UI will be available at: http://54.236.135.105:3000"
    echo ""
    echo "Press Ctrl+C to stop the server"
    echo ""

    if command -v pnpm &> /dev/null; then
        pnpm dev $HOSTNAME_FLAG
    else
        npm run dev -- $HOSTNAME_FLAG
    fi
fi

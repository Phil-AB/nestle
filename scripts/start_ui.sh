#!/bin/bash

# Start Next.js Frontend
# Usage: ./start_ui.sh

set -e

echo "=========================================="
echo "  Starting Nestle UI Frontend"
echo "=========================================="
echo ""

# Get the project root directory (parent of scripts directory)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Change to project root
cd "$PROJECT_ROOT"
echo "Working directory: $PROJECT_ROOT"

# Activate conda environment for Python dependencies (if any)
echo "Activating conda environment: nestle..."
eval "$(conda shell.bash hook)"
conda activate nestle 2>/dev/null || echo "Warning: Could not activate conda environment 'nestle'"

# Navigate to UI directory
cd src/ui

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "Node modules not found. Installing dependencies..."
    echo ""

    # Check if pnpm is available
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

    # Detect public IP for cloud environments
    PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo "")
    API_URL=${NEXT_PUBLIC_API_URL:-"http://localhost:8000/api/v1"}

    # Use public IP if available and not overridden
    if [ -n "$PUBLIC_IP" ] && [ "$API_URL" = "http://localhost:8000/api/v1" ]; then
        API_URL="http://$PUBLIC_IP:8000/api/v1"
        echo "Detected public IP: $PUBLIC_IP, using API URL: $API_URL"
    fi

    cat > .env.local << EOF
NEXT_PUBLIC_API_URL=$API_URL
NEXT_PUBLIC_API_KEY=dev-key-12345
EOF
    echo "Created .env.local with API URL: $API_URL"
fi

echo ""
echo "Starting Next.js development server..."
echo "UI will be available at: http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start Next.js dev server
if command -v pnpm &> /dev/null; then
    pnpm dev
else
    npm run dev
fi

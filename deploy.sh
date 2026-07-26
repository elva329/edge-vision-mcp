#!/usr/bin/env bash
set -euo pipefail

echo "=== Edge Vision MCP Deployment ==="
echo ""
echo "Platform:"
echo "  1) Fly.io (recommended)"
echo "  2) Render.com"
echo "  3) Docker Hub"
echo ""
read -p "Select platform (1-3): " PLATFORM

echo ""
echo "Building frontend..."
cd src/agui && npm run build && cd ../..

echo ""
echo "Building Docker image..."
docker build -t edge-vision-mcp .

case "$PLATFORM" in
  1)
    echo ""
    echo "Deploying to Fly.io..."
    if ! command -v fly &>/dev/null; then
      echo "Installing Fly CLI..."
      curl -L https://fly.io/install.sh | sh
    fi
    fly auth login
    fly launch --no-deploy
    fly deploy
    echo ""
    echo "Done. Open with: fly open"
    ;;
  2)
    echo ""
    echo "Push to Docker Hub or Render..."
    echo "Render uses Dockerfile directly. In Render dashboard:"
    echo "  - Connect repo"
    echo "  - Set Docker as environment"
    echo "  - Set start command: python3 main.py --host 0.0.0.0 --port 9000"
    ;;
  3)
    echo ""
    read -p "Docker Hub username: " USERNAME
    docker tag edge-vision-mcp "$USERNAME/edge-vision-mcp:latest"
    docker push "$USERNAME/edge-vision-mcp:latest"
    echo ""
    echo "Image pushed. Run anywhere with:"
    echo "  docker run -p 9000:9000 -p 8080:8080 $USERNAME/edge-vision-mcp:latest"
    ;;
esac

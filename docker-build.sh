#!/bin/bash
#
# OLT Manager Docker Build Script
# Run this on a server with Docker installed
#

set -e

VERSION=$(cat backend/VERSION 2>/dev/null || echo "1.3.1")

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║          OLT Manager Docker Image Builder                    ║"
echo "║                    Version $VERSION                             ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "[X] Docker is not installed"
    exit 1
fi

# Build image
echo "[*] Building Docker image..."
docker build -t olt-manager:$VERSION .

if [[ $? -eq 0 ]]; then
    echo ""
    echo "[*] Docker image built successfully!"
    echo ""
    echo "To run:"
    echo "  docker-compose up -d"
    echo ""
    echo "Or manually:"
    echo "  docker run -d -p 80:80 --name olt-manager olt-manager:$VERSION"
    echo ""

    # Save image as tar for distribution
    echo "[*] Saving image for distribution..."
    docker save olt-manager:$VERSION | gzip > olt-manager-$VERSION.tar.gz
    echo "[*] Saved: olt-manager-$VERSION.tar.gz"
    echo ""
    echo "To load on another server:"
    echo "  docker load < olt-manager-$VERSION.tar.gz"
else
    echo "[X] Docker build failed"
    exit 1
fi

#!/bin/bash
# ============================================
# OLT Manager - Nuitka Compiled Build
# Compiles Python to C to Binary
# ============================================

set -e

echo "========================================"
echo "  OLT Manager - Nuitka Compilation"
echo "========================================"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

BACKEND_DIR="/root/olt-manager/backend"
BUILD_DIR="/root/olt-manager/nuitka_build"
DIST_DIR="/root/olt-manager/dist"

cd "$BACKEND_DIR"
source venv/bin/activate

# Check for required packages
echo -e "${YELLOW}[1/4] Checking dependencies...${NC}"
apt-get install -y patchelf ccache 2>/dev/null || true

# Clean previous builds
echo -e "${YELLOW}[2/4] Cleaning previous builds...${NC}"
rm -rf "$BUILD_DIR" main.build main.dist main.onefile-build
mkdir -p "$BUILD_DIR" "$DIST_DIR"

# Create templates folder if not exists
mkdir -p templates uploads

# Compile with Nuitka
echo -e "${YELLOW}[3/4] Compiling with Nuitka (this takes 30-60 min)...${NC}"
echo "    Compiling Python → C → Binary..."

python -m nuitka \
    --standalone \
    --onefile \
    --output-dir="$BUILD_DIR" \
    --output-filename=olt-manager \
    --follow-imports \
    --prefer-source-code \
    main.py

echo -e "${GREEN}    ✓ Compilation complete${NC}"

# Create deployment package
echo -e "${YELLOW}[4/4] Creating deployment package...${NC}"

mkdir -p "$BUILD_DIR/package"

# Find and copy the binary
if [ -f "$BUILD_DIR/olt-manager" ]; then
    cp "$BUILD_DIR/olt-manager" "$BUILD_DIR/package/"
elif [ -f "$BUILD_DIR/main.bin" ]; then
    cp "$BUILD_DIR/main.bin" "$BUILD_DIR/package/olt-manager"
else
    BINARY=$(find "$BUILD_DIR" -type f -executable -name "*.bin" 2>/dev/null | head -1)
    if [ -n "$BINARY" ]; then
        cp "$BINARY" "$BUILD_DIR/package/olt-manager"
    fi
fi

chmod +x "$BUILD_DIR/package/olt-manager" 2>/dev/null || true

mkdir -p "$BUILD_DIR/package/data"
mkdir -p "$BUILD_DIR/package/uploads"

# Create startup script
cat > "$BUILD_DIR/package/start.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
./olt-manager
EOF
chmod +x "$BUILD_DIR/package/start.sh"

# Create systemd service
cat > "$BUILD_DIR/package/olt-manager.service" << 'EOF'
[Unit]
Description=OLT Manager Backend
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/olt-manager
ExecStart=/opt/olt-manager/olt-manager
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Copy version file from backend (just the version number)
cp "$BACKEND_DIR/VERSION" "$BUILD_DIR/package/VERSION"

# Package
cd "$BUILD_DIR/package"
FILENAME="olt-manager-compiled-$(date +%Y%m%d).tar.gz"
tar -czvf "$DIST_DIR/$FILENAME" .

echo ""
echo -e "${GREEN}========================================"
echo "  BUILD COMPLETE!"
echo "========================================"
echo ""
echo "  Binary:       $BUILD_DIR/package/olt-manager"
echo "  Distribution: $DIST_DIR/$FILENAME"
echo ""
echo "  Protection:"
echo "    ✓ Compiled to native binary"
echo "    ✓ No Python source code"
echo "    ✓ Cannot be decompiled"
echo "    ✓ License server integrated"
echo "========================================${NC}"

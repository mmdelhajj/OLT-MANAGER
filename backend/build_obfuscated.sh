#!/bin/bash
# ============================================
# OLT Manager - Quick Obfuscated Build
# Fast code protection (5 minutes)
# ============================================

set -e

echo "========================================"
echo "  OLT Manager - Quick Obfuscated Build"
echo "========================================"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

BACKEND_DIR="/root/olt-manager/backend"
BUILD_DIR="/root/olt-manager/obfuscated_build"
DIST_DIR="/root/olt-manager/dist"

cd "$BACKEND_DIR"
source venv/bin/activate

# Install pyminifier
pip install python-minifier 2>/dev/null || true

# Clean previous builds
echo -e "${YELLOW}[1/4] Cleaning previous builds...${NC}"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR" "$DIST_DIR"

# Obfuscate all Python files
echo -e "${YELLOW}[2/4] Obfuscating Python files...${NC}"

for pyfile in main.py auth.py config.py license_manager.py models.py \
              olt_connector.py olt_web_scraper.py schemas.py \
              trap_receiver.py tunnel_manager.py run_server.py; do
    if [ -f "$pyfile" ]; then
        echo "    Processing $pyfile..."
        python -m python_minifier "$pyfile" > "$BUILD_DIR/$pyfile"
    fi
done

echo -e "${GREEN}    ✓ Code obfuscated${NC}"

# Copy additional files
echo -e "${YELLOW}[3/4] Copying additional files...${NC}"
cp -r templates "$BUILD_DIR/" 2>/dev/null || true
mkdir -p "$BUILD_DIR/uploads"
mkdir -p "$BUILD_DIR/data"

# Copy venv or create requirements
cat > "$BUILD_DIR/requirements.txt" << 'EOF'
fastapi>=0.104.0
uvicorn>=0.24.0
sqlalchemy>=2.0.0
python-jose>=3.3.0
passlib>=1.7.4
bcrypt>=4.0.0
python-multipart>=0.0.6
pysnmp>=4.4.12
aiohttp>=3.9.0
requests>=2.31.0
paramiko>=3.4.0
boto3>=1.34.0
jinja2>=3.1.0
aiofiles>=23.2.0
EOF

# Create install script
cat > "$BUILD_DIR/install.sh" << 'INSTALLEOF'
#!/bin/bash
echo "Installing OLT Manager..."
apt-get update
apt-get install -y python3 python3-pip python3-venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
echo "Installation complete! Run: source venv/bin/activate && python main.py"
INSTALLEOF
chmod +x "$BUILD_DIR/install.sh"

# Create version info
cat > "$BUILD_DIR/VERSION" << EOF
OLT Manager Obfuscated Build
Built: $(date '+%Y-%m-%d %H:%M:%S')
Protection: Minified + Obfuscated
EOF

echo -e "${GREEN}    ✓ Files copied${NC}"

# Package
echo -e "${YELLOW}[4/4] Creating package...${NC}"
cd "$BUILD_DIR"
FILENAME="olt-manager-obfuscated-$(date +%Y%m%d).tar.gz"
tar -czvf "$DIST_DIR/$FILENAME" .

echo ""
echo -e "${GREEN}========================================"
echo "  BUILD COMPLETE!"
echo "========================================"
echo ""
echo "  Build:        $BUILD_DIR"
echo "  Distribution: $DIST_DIR/$FILENAME"
echo ""
echo "  Protection:"
echo "    ✓ Code minified (unreadable)"
echo "    ✓ Variable names removed"
echo "    ✓ Comments removed"
echo "    ✓ License server integrated"
echo "========================================${NC}"

echo ""
echo "Sample of obfuscated code:"
head -5 "$BUILD_DIR/main.py"

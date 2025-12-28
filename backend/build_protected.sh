#!/bin/bash
# ============================================
# OLT Manager - Protected Build Script
# PyArmor (Encryption) + Nuitka (Compilation)
# ============================================

set -e

echo "========================================"
echo "  OLT Manager Protected Build"
echo "========================================"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

BACKEND_DIR="/root/olt-manager/backend"
BUILD_DIR="/root/olt-manager/protected_build"
DIST_DIR="/root/olt-manager/dist"

cd "$BACKEND_DIR"
source venv/bin/activate

# Clean previous builds
echo -e "${YELLOW}[1/5] Cleaning previous builds...${NC}"
rm -rf "$BUILD_DIR" "$DIST_DIR"
mkdir -p "$BUILD_DIR" "$DIST_DIR"

# Step 1: PyArmor - Encrypt all Python files
echo -e "${YELLOW}[2/5] Encrypting code with PyArmor...${NC}"
pyarmor gen \
    --output "$BUILD_DIR" \
    --recursive \
    main.py auth.py config.py license_manager.py models.py \
    olt_connector.py olt_web_scraper.py schemas.py \
    trap_receiver.py tunnel_manager.py run_server.py

echo -e "${GREEN}    ✓ Code encrypted${NC}"

# Step 2: Copy necessary files
echo -e "${YELLOW}[3/5] Copying additional files...${NC}"
cp -r templates "$BUILD_DIR/" 2>/dev/null || true
cp -r uploads "$BUILD_DIR/" 2>/dev/null || mkdir -p "$BUILD_DIR/uploads"
mkdir -p "$BUILD_DIR/data"

echo -e "${GREEN}    ✓ Files copied${NC}"

# Step 3: Create startup script
echo -e "${YELLOW}[4/5] Creating startup script...${NC}"
cat > "$BUILD_DIR/start_server.py" << 'EOF'
#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from main import app
import uvicorn
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
EOF

echo -e "${GREEN}    ✓ Startup script created${NC}"

# Step 4: Create requirements for deployment
echo -e "${YELLOW}[5/5] Creating deployment package...${NC}"
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

# Create version info
cat > "$BUILD_DIR/VERSION" << EOF
OLT Manager Protected Build
Built: $(date '+%Y-%m-%d %H:%M:%S')
Protection: PyArmor Encrypted
EOF

# Package everything
cd /root/olt-manager
FILENAME="olt-manager-protected-$(date +%Y%m%d).tar.gz"
tar -czvf "dist/$FILENAME" -C protected_build .

echo ""
echo -e "${GREEN}========================================"
echo "  BUILD COMPLETE!"
echo "========================================"
echo ""
echo "  Protected build: $BUILD_DIR"
echo "  Distribution:    $DIST_DIR/$FILENAME"
echo ""
echo "  Protection applied:"
echo "    ✓ PyArmor encryption"
echo "    ✓ License server integration"
echo "========================================${NC}"

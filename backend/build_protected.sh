#!/bin/bash
# Build protected OLT Manager distribution
# This script obfuscates and packages the code

set -e

echo "=========================================="
echo "  OLT Manager Protected Build"
echo "=========================================="

# Check dependencies
command -v pyarmor >/dev/null 2>&1 || { echo "Installing PyArmor..."; pip install pyarmor; }

# Clean previous builds
rm -rf dist/ build/ protected/
mkdir -p protected

# Step 1: Obfuscate Python files with PyArmor
echo "[1/4] Obfuscating Python code..."
pyarmor gen \
    --output protected/ \
    --recursive \
    --enable-jit \
    --assert-call \
    --private \
    *.py

# Step 2: Copy non-Python files
echo "[2/4] Copying assets..."
cp -r uploads protected/ 2>/dev/null || mkdir -p protected/uploads
cp VERSION protected/ 2>/dev/null || echo "1.0.0" > protected/VERSION
cp requirements.txt protected/

# Step 3: Create runner script
echo "[3/4] Creating launcher..."
cat > protected/run_olt_manager.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
export PYTHONPATH="$(pwd)"
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
EOF
chmod +x protected/run_olt_manager.sh

# Step 4: Create tarball
echo "[4/4] Creating distribution package..."
VERSION=$(cat VERSION 2>/dev/null || echo "1.0.0")
PACKAGE_NAME="olt-manager-${VERSION}-protected.tar.gz"
tar -czf "$PACKAGE_NAME" -C protected .

echo ""
echo "=========================================="
echo "  Build Complete!"
echo "=========================================="
echo "  Package: $PACKAGE_NAME"
echo "  Size: $(du -h $PACKAGE_NAME | cut -f1)"
echo ""
echo "  Protection features:"
echo "  - Code obfuscation (PyArmor)"
echo "  - License validation"
echo "  - Hardware ID binding"
echo "=========================================="

#!/usr/bin/env python3
"""
Build script for OLT Manager - Creates encrypted binary distribution
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

# Configuration
PROJECT_ROOT = Path("/root/olt-manager")
BACKEND_DIR = PROJECT_ROOT / "backend"
FRONTEND_DIR = PROJECT_ROOT / "frontend"
BUILD_DIR = PROJECT_ROOT / "dist"
RELEASE_DIR = PROJECT_ROOT / "release"

# Your license server URL (customers will validate against this)
LICENSE_SERVER_URL = "https://license.yourcompany.com"  # Change this to your domain

def clean_build():
    """Clean previous builds"""
    print("🧹 Cleaning previous builds...")
    for d in [BUILD_DIR, RELEASE_DIR]:
        if d.exists():
            shutil.rmtree(d)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)

def build_frontend():
    """Build React frontend"""
    print("🔨 Building frontend...")
    os.chdir(FRONTEND_DIR)
    subprocess.run(["npm", "run", "build"], check=True, env={
        **os.environ,
        "REACT_APP_API_URL": "",  # Relative URLs for production
        "DISABLE_ESLINT_PLUGIN": "true"
    })
    # Copy build to release
    shutil.copytree(FRONTEND_DIR / "build", RELEASE_DIR / "frontend")
    print("✅ Frontend built")

def compile_backend():
    """Compile Python backend to binary using Nuitka"""
    print("🔨 Compiling backend to binary (this takes 10-20 minutes)...")
    os.chdir(BACKEND_DIR)

    # Create a wrapper that includes all modules
    wrapper = BACKEND_DIR / "olt_manager_compiled.py"
    wrapper.write_text('''#!/usr/bin/env python3
"""OLT Manager - Compiled Binary"""
import uvicorn
from main import app

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
''')

    # Compile with Nuitka
    cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        "--onefile",
        "--follow-imports",
        "--include-package=uvicorn",
        "--include-package=fastapi",
        "--include-package=sqlalchemy",
        "--include-package=pydantic",
        "--include-package=pysnmp",
        "--include-package=requests",
        "--include-package=jose",
        "--include-package=passlib",
        "--include-package=multipart",
        f"--output-dir={BUILD_DIR}",
        "--output-filename=olt-manager-backend",
        "--remove-output",
        str(wrapper)
    ]

    subprocess.run(cmd, check=True)

    # Copy binary to release
    shutil.copy(BUILD_DIR / "olt-manager-backend", RELEASE_DIR / "olt-manager-backend")
    os.chmod(RELEASE_DIR / "olt-manager-backend", 0o755)

    # Clean up wrapper
    wrapper.unlink()
    print("✅ Backend compiled to binary")

def create_install_script():
    """Create installation script for customers"""
    install_script = RELEASE_DIR / "install.sh"
    install_script.write_text(f'''#!/bin/bash
# OLT Manager Installation Script
# Run as root: sudo bash install.sh

set -e

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║           OLT Manager - Installation                          ║"
echo "╚══════════════════════════════════════════════════════════════╝"

# Check root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run as root (sudo bash install.sh)"
    exit 1
fi

# Get license key
if [ -z "$1" ]; then
    echo ""
    read -p "Enter your license key: " LICENSE_KEY
else
    LICENSE_KEY="$1"
fi

if [ -z "$LICENSE_KEY" ]; then
    echo "❌ License key is required"
    exit 1
fi

INSTALL_DIR="/opt/olt-manager"
WEB_DIR="/var/www/olt-manager"

echo ""
echo "📦 Installing OLT Manager..."

# Create directories
mkdir -p $INSTALL_DIR
mkdir -p $WEB_DIR
mkdir -p /etc/olt-manager
mkdir -p /var/lib/olt-manager

# Copy files
cp olt-manager-backend $INSTALL_DIR/
chmod +x $INSTALL_DIR/olt-manager-backend
cp -r frontend/* $WEB_DIR/

# Save license key
echo "$LICENSE_KEY" > /etc/olt-manager/license.key
chmod 600 /etc/olt-manager/license.key

# Create systemd service
cat > /etc/systemd/system/olt-manager.service << 'EOF'
[Unit]
Description=OLT Manager Backend
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/olt-manager
Environment=LICENSE_SERVER_URL={LICENSE_SERVER_URL}
ExecStart=/opt/olt-manager/olt-manager-backend
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Create nginx config
cat > /etc/nginx/sites-available/olt-manager << 'NGINX'
server {{
    listen 80;
    server_name _;

    root /var/www/olt-manager;
    index index.html;

    location / {{
        try_files $uri $uri/ /index.html;
    }}

    location /api {{
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }}
}}
NGINX

# Enable site
ln -sf /etc/nginx/sites-available/olt-manager /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true

# Install nginx if not present
if ! command -v nginx &> /dev/null; then
    apt-get update
    apt-get install -y nginx
fi

# Start services
systemctl daemon-reload
systemctl enable olt-manager
systemctl start olt-manager
systemctl restart nginx

echo ""
echo "✅ OLT Manager installed successfully!"
echo ""
echo "📋 Access the web interface at: http://$(hostname -I | awk '{{print $1}}')"
echo "📋 Default login: admin / admin123"
echo ""
echo "⚠️  Please change the default password after first login!"
''')
    os.chmod(install_script, 0o755)
    print("✅ Install script created")

def create_package():
    """Create distribution package"""
    print("📦 Creating distribution package...")
    os.chdir(PROJECT_ROOT)

    # Create tar.gz
    package_name = "olt-manager-v1.0"
    shutil.make_archive(package_name, 'gztar', RELEASE_DIR)

    final_package = PROJECT_ROOT / f"{package_name}.tar.gz"
    print(f"✅ Package created: {final_package}")
    print(f"   Size: {final_package.stat().st_size / 1024 / 1024:.1f} MB")

def main():
    print("=" * 60)
    print("  OLT Manager - Build Release Package")
    print("=" * 60)

    clean_build()
    build_frontend()
    compile_backend()  # This takes long time
    create_install_script()
    create_package()

    print("")
    print("=" * 60)
    print("  BUILD COMPLETE!")
    print("=" * 60)
    print("")
    print("📦 Distribution package: /root/olt-manager/olt-manager-v1.0.tar.gz")
    print("")
    print("To install on customer server:")
    print("  1. Copy olt-manager-v1.0.tar.gz to customer server")
    print("  2. tar -xzf olt-manager-v1.0.tar.gz")
    print("  3. sudo bash install.sh LICENSE-KEY-HERE")

if __name__ == "__main__":
    main()

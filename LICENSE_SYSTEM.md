# OLT Manager - License & Protection System

## Overview

This document explains how to protect your OLT Manager software for commercial sale.

---

## 1. License System Architecture

```
┌─────────────────┐     HTTPS      ┌──────────────────┐
│  Customer's     │◄──────────────►│  Your License    │
│  OLT Manager    │                │  Server          │
│  Installation   │                │  (license.yourco.com)
└─────────────────┘                └──────────────────┘
        │                                  │
        │ Validates on startup             │ You manage licenses
        │ Caches for offline (7 days)      │ Generate keys, extend, revoke
        │                                  │
        ▼                                  ▼
   Hardware ID                      licenses.json database
   (MAC + Machine ID)
```

---

## 2. Setting Up Your License Server

### Step 1: Deploy License Server

```bash
# On your server (e.g., license.yourcompany.com)
cd /opt
git clone your-repo/license-server
cd license-server

# Install dependencies
pip3 install flask flask-cors

# Set admin secret key
export LICENSE_SECRET="your-super-secret-admin-key-here"

# Run with gunicorn for production
pip3 install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 license_server:app
```

### Step 2: Setup SSL with Nginx

```nginx
server {
    listen 443 ssl;
    server_name license.yourcompany.com;

    ssl_certificate /etc/letsencrypt/live/license.yourcompany.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/license.yourcompany.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## 3. Managing Licenses

### Create a New License

```bash
curl -X POST https://license.yourcompany.com/api/licenses \
  -H "X-Admin-Key: your-secret-key" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_name": "ABC Telecom",
    "customer_email": "admin@abctelecom.com",
    "max_olts": 10,
    "max_onus": 5000,
    "max_users": 20,
    "validity_days": 365,
    "features": ["basic", "traffic", "diagrams", "whatsapp"],
    "license_type": "enterprise"
  }'
```

**Response:**
```json
{
  "license_key": "OLT-A1B2C3D4-E5F6G7H8-I9J0K1L2",
  "customer_name": "ABC Telecom",
  "max_olts": 10,
  "expires_at": "2026-12-06T00:00:00"
}
```

### List All Licenses

```bash
curl -H "X-Admin-Key: your-secret-key" \
  https://license.yourcompany.com/api/licenses
```

### Extend a License

```bash
curl -X PUT https://license.yourcompany.com/api/licenses/OLT-A1B2C3D4-E5F6G7H8-I9J0K1L2 \
  -H "X-Admin-Key: your-secret-key" \
  -H "Content-Type: application/json" \
  -d '{"extend_days": 365}'
```

### Revoke a License

```bash
curl -X DELETE https://license.yourcompany.com/api/licenses/OLT-A1B2C3D4-E5F6G7H8-I9J0K1L2 \
  -H "X-Admin-Key: your-secret-key"
```

### Reset Hardware Binding

If customer moves to new server:

```bash
curl -X POST https://license.yourcompany.com/api/licenses/OLT-A1B2C3D4-E5F6G7H8-I9J0K1L2/reset \
  -H "X-Admin-Key: your-secret-key"
```

---

## 4. Customer Installation

### Method 1: Environment Variable

Edit `/etc/systemd/system/olt-backend.service`:

```ini
[Service]
Environment=OLT_LICENSE_KEY=OLT-A1B2C3D4-E5F6G7H8-I9J0K1L2
Environment=LICENSE_SERVER_URL=https://license.yourcompany.com
# Remove or comment out dev mode:
# Environment=OLT_DEV_MODE=true
```

### Method 2: License File

```bash
mkdir -p /etc/olt-manager
echo "OLT-A1B2C3D4-E5F6G7H8-I9J0K1L2" > /etc/olt-manager/license.key
chmod 600 /etc/olt-manager/license.key
```

---

## 5. License Tiers (Example Pricing)

| Feature | Basic ($99/mo) | Professional ($299/mo) | Enterprise ($599/mo) |
|---------|----------------|------------------------|---------------------|
| Max OLTs | 2 | 10 | Unlimited |
| Max ONUs | 200 | 2000 | Unlimited |
| Max Users | 3 | 10 | Unlimited |
| Traffic Monitor | ❌ | ✅ | ✅ |
| Splitter Diagrams | ❌ | ✅ | ✅ |
| WhatsApp Alerts | ❌ | ✅ | ✅ |
| Priority Support | ❌ | ❌ | ✅ |

---

## 6. Code Protection Options

### Option A: Obfuscation (Basic)

```bash
# Install pyarmor
pip install pyarmor

# Obfuscate Python code
pyarmor gen --pack onefile backend/

# This creates encrypted .pyc files that are harder to read
```

### Option B: Compile to Binary (Better)

```bash
# Install PyInstaller
pip install pyinstaller

# Create single executable
pyinstaller --onefile --hidden-import uvicorn main.py
```

### Option C: Nuitka (Best - Compiles to C)

```bash
# Install Nuitka
pip install nuitka

# Compile to native binary
python -m nuitka --standalone --onefile main.py
```

### Option D: Docker with Encrypted Layer

```dockerfile
FROM python:3.11-slim
# Your code is inside the image, harder to extract
COPY --chown=root:root backend/ /app/
RUN chmod -R 500 /app/
```

---

## 7. Security Recommendations

1. **Always use HTTPS** for license server
2. **Keep SECRET_KEY secure** - never commit to git
3. **Rate limit** the validation endpoint
4. **Log all license checks** for audit
5. **Monitor for suspicious activity** (many failed validations)
6. **Use short cache periods** (7 days max offline)
7. **Require hardware binding** to prevent key sharing

---

## 8. Quick Test

```bash
# Test license validation locally
curl -X POST http://localhost:5000/api/validate \
  -H "Content-Type: application/json" \
  -d '{
    "license_key": "OLT-TEST-KEY",
    "hardware_id": "abc123",
    "product": "olt-manager",
    "version": "1.0.0"
  }'
```

---

## 9. Files Created

- `/root/olt-manager/backend/license_manager.py` - License validation module
- `/root/olt-manager/license-server/license_server.py` - Your license server
- `/etc/systemd/system/olt-backend.service` - Updated with license config

---

## Support

For issues with the license system, check logs:

```bash
journalctl -u olt-backend -f | grep -i license
```

# OLT Manager - License Server

Deploy this on your public IP server to manage customer licenses.

## Quick Install

```bash
sudo bash install_license_server.sh
```

This will:
1. Install Python, Flask, Nginx
2. Set up the license server as a systemd service
3. Generate an admin API key
4. Configure Nginx as reverse proxy

## Manual Install

```bash
pip3 install flask flask-cors gunicorn

# Set your admin key
export LICENSE_SECRET="your-super-secret-key"

# Run
gunicorn -w 2 -b 0.0.0.0:5000 license_server:app
```

## API Reference

### Public Endpoint (for customer installations)

**Validate License**
```bash
POST /api/validate
{
    "license_key": "OLT-XXXX-XXXX-XXXX",
    "hardware_id": "abc123..."
}
```

### Admin Endpoints (require X-Admin-Key header)

**Create License**
```bash
curl -X POST http://YOUR-SERVER/api/licenses \
  -H "X-Admin-Key: YOUR-KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_name": "ABC Company",
    "customer_email": "admin@abc.com",
    "max_olts": 10,
    "max_onus": 5000,
    "max_users": 20,
    "validity_days": 365,
    "features": ["basic", "traffic", "diagrams", "whatsapp"],
    "license_type": "enterprise"
  }'
```

**List Licenses**
```bash
curl -H "X-Admin-Key: YOUR-KEY" http://YOUR-SERVER/api/licenses
```

**Extend License**
```bash
curl -X PUT http://YOUR-SERVER/api/licenses/OLT-XXXX-XXXX-XXXX \
  -H "X-Admin-Key: YOUR-KEY" \
  -H "Content-Type: application/json" \
  -d '{"extend_days": 365}'
```

**Reset Hardware Binding**
```bash
curl -X POST http://YOUR-SERVER/api/licenses/OLT-XXXX-XXXX-XXXX/reset \
  -H "X-Admin-Key: YOUR-KEY"
```

**Revoke License**
```bash
curl -X DELETE http://YOUR-SERVER/api/licenses/OLT-XXXX-XXXX-XXXX \
  -H "X-Admin-Key: YOUR-KEY"
```

## SSL Setup (Recommended)

```bash
apt install certbot python3-certbot-nginx
certbot --nginx -d license.yourdomain.com
```

## License Features

| Feature | Description |
|---------|-------------|
| basic | Core OLT/ONU management |
| traffic | Traffic monitoring graphs |
| diagrams | Splitter diagram simulator |
| whatsapp | WhatsApp notifications |
| all | All features |

## License Types

- `basic` - Entry level
- `standard` - Standard tier
- `professional` - Professional tier
- `enterprise` - Full features

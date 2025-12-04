# OLT Manager

A web-based dashboard for managing EPON/GPON OLTs and ONUs. Designed for ISPs to monitor and manage their fiber network equipment.

## Quick Install (One Command)

```bash
curl -sSL https://raw.githubusercontent.com/mmdelhajj/OLT-MANAGER/main/install.sh | sudo bash
```

Or download and run:

```bash
wget https://raw.githubusercontent.com/mmdelhajj/OLT-MANAGER/main/install.sh
chmod +x install.sh
sudo ./install.sh
```

### Update Existing Installation

```bash
sudo /opt/olt-manager/install.sh --update
```

### Uninstall

```bash
sudo /opt/olt-manager/install.sh --uninstall
```

## Features

- **Dashboard Overview**: Total OLTs, ONUs, online/offline counts with statistics
- **OLT Management**: Add, edit, delete OLTs with SSH/SNMP credentials
- **ONU Monitoring**: View all ONUs with serial number, description, optical power, distance
- **Region Management**: Group ONUs by region with color coding
- **User Management**: Admin and Operator roles with OLT access restrictions
- **Live Traffic**: Real-time traffic monitoring via WebSocket
- **SNMP Trap Receiver**: Automatic ONU status change detection
- **WhatsApp Notifications**: Alerts via WhatsApp API
- **Search**: Find customers by serial number, description, or MAC address
- **Auto-Polling**: Configurable automatic polling interval
- **Image Upload**: Attach photos to ONU records

## Default Login

- **Username**: `admin`
- **Password**: `admin`

> ⚠️ **Change the default password after first login!**

## Supported Equipment

- VSOL V1600D8 (8 PON ports)
- VSOL V1601E04 (4 PON ports)
- Other VSOL EPON/GPON OLTs with similar CLI/SNMP

## System Requirements

- Ubuntu 20.04+ or Debian 11+
- 1GB RAM minimum
- 10GB disk space
- Root access

## Tech Stack

- **Backend**: Python FastAPI, SQLAlchemy, Paramiko, pysnmp
- **Frontend**: React, Tailwind CSS
- **Database**: SQLite
- **Web Server**: Nginx
- **Deployment**: Systemd service

## Service Management

```bash
# Check status
systemctl status olt-backend

# View logs
journalctl -u olt-backend -f

# Restart service
systemctl restart olt-backend

# Stop service
systemctl stop olt-backend
```

## API Endpoints

### Dashboard
- `GET /api/dashboard` - Get statistics

### OLTs
- `GET /api/olts` - List all OLTs
- `GET /api/olts/{id}` - Get specific OLT
- `POST /api/olts` - Add new OLT
- `PUT /api/olts/{id}` - Update OLT
- `DELETE /api/olts/{id}` - Delete OLT
- `POST /api/olts/{id}/poll` - Manual poll
- `GET /api/olts/{id}/traffic` - Get traffic data

### ONUs
- `GET /api/onus` - List all ONUs (supports filters)
- `GET /api/onus/search?q=query` - Search ONUs
- `GET /api/onus/{id}` - Get specific ONU
- `PUT /api/onus/{id}` - Update ONU
- `DELETE /api/onus/{id}` - Delete ONU
- `POST /api/onus/{id}/image` - Upload image
- `DELETE /api/onus/{id}/image` - Delete image

### Regions
- `GET /api/regions` - List all regions
- `POST /api/regions` - Create region
- `PUT /api/regions/{id}` - Update region
- `DELETE /api/regions/{id}` - Delete region

### Users
- `GET /api/users` - List all users
- `POST /api/users` - Create user
- `PUT /api/users/{id}` - Update user
- `DELETE /api/users/{id}` - Delete user

### Authentication
- `POST /api/auth/login` - Login
- `GET /api/auth/me` - Get current user
- `POST /api/auth/change-password` - Change password

### Settings
- `GET /api/settings` - Get settings
- `PUT /api/settings` - Update settings

### Traffic & Monitoring
- `GET /api/traffic/all` - All OLTs traffic
- `WS /ws/traffic/{olt_id}` - Live traffic WebSocket
- `GET /api/traffic/history/olt/{id}` - Traffic history

### Health & Status
- `GET /api/health` - Health check
- `GET /api/trap/status` - SNMP trap receiver status

## Configuration

Settings can be modified via the web interface under Settings page:

| Setting | Description |
|---------|-------------|
| System Name | Display name for the system |
| Refresh Interval | Dashboard auto-refresh (seconds) |
| Polling Interval | OLT polling interval (seconds) |
| WhatsApp Enabled | Enable WhatsApp notifications |
| WhatsApp Recipients | Phone numbers for alerts |
| SNMP Trap Port | Port for SNMP trap receiver (default: 162) |

## Project Structure

```
olt-manager/
├── backend/
│   ├── main.py           # FastAPI app & endpoints
│   ├── models.py         # Database models
│   ├── schemas.py        # Pydantic schemas
│   ├── olt_connector.py  # SSH/SNMP connection & parsing
│   ├── trap_receiver.py  # SNMP trap handler
│   ├── auth.py           # Authentication
│   ├── config.py         # Configuration
│   ├── requirements.txt
│   └── uploads/          # ONU images
├── frontend/
│   ├── src/
│   │   ├── App.js        # Main React component
│   │   ├── api.js        # API client
│   │   └── index.js      # Entry point
│   ├── public/
│   └── package.json
├── install.sh            # One-click installer
├── docker-compose.yml    # Docker deployment
└── README.md
```

## Troubleshooting

### OLT shows offline
- Check network connectivity to OLT
- Verify SSH/SNMP credentials
- Check OLT IP address is reachable
- View error details in dashboard

### Backend won't start
```bash
journalctl -u olt-backend -n 100
```

### Port 162 in use (SNMP traps)
```bash
lsof -i :162
# Stop conflicting service or change trap port in settings
```

### Reset admin password
```bash
cd /opt/olt-manager/backend
source venv/bin/activate
python3 -c "
from models import init_db, get_db, User
from auth import get_password_hash
db = next(get_db())
user = db.query(User).filter(User.username == 'admin').first()
user.password_hash = get_password_hash('admin')
db.commit()
print('Password reset to: admin')
"
```

## Security Notes

- Change default admin password immediately
- Use HTTPS in production (configure nginx with SSL)
- Restrict network access to management interface
- OLT credentials are stored in the database

## License

MIT License

## Support

For issues and feature requests, please visit:
https://github.com/mmdelhajj/OLT-MANAGER/issues

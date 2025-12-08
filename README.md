# OLT Manager Pro

A professional web-based dashboard for managing EPON/GPON OLTs and ONUs. Designed for ISPs to monitor and manage their fiber network equipment.

## Quick Install (One Command)

```bash
curl -sSL https://raw.githubusercontent.com/mmdelhajj/OLT-MANAGER/main/install.sh | sudo bash
```

**Includes 7-Day FREE Trial!** - No registration required, automatic license activation.

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

## System Requirements

| Requirement | Specification |
|-------------|---------------|
| **Operating System** | Ubuntu 22.04 LTS (Recommended) / Ubuntu 20.04+ / Debian 11+ |
| **RAM** | 1GB minimum, 2GB recommended |
| **Disk Space** | 10GB minimum |
| **Access** | Root access required |
| **Network** | Internet connection for installation |

## Default Login

| Field | Value |
|-------|-------|
| **Username** | `admin` |
| **Password** | `admin123` |

> **Important:** Change the default password after first login!

## Features

### Core Features
- **Dashboard Overview**: Real-time statistics for OLTs, ONUs, online/offline counts
- **OLT Management**: Add, edit, delete OLTs with SSH/SNMP credentials
- **ONU Monitoring**: View all ONUs with serial number, description, optical power, distance
- **Live Traffic Graphs**: Real-time bandwidth monitoring for OLTs, PON ports, and ONUs
- **Auto-Polling**: Configurable automatic polling interval

### Organization
- **Region Management**: Group ONUs by region with custom color coding
- **User Management**: Admin and Operator roles with OLT access restrictions
- **Search**: Find customers by serial number, description, or MAC address

### Monitoring & Alerts
- **SNMP Trap Receiver**: Automatic ONU status change detection
- **WhatsApp Notifications**: Instant alerts via WhatsApp API
- **Traffic History**: Historical bandwidth data with graphs

### Additional Features
- **Image Upload**: Attach photos to ONU records
- **Splitter Simulator**: Visual network planning tool
- **Auto Updates**: One-click system updates from dashboard
- **Map Integration**: Location tracking for ONUs and regions

## Supported Equipment

### VSOL GPON OLTs (1 PON Port)
| Model | PON Ports | Notes |
|-------|-----------|-------|
| V1600GS | 1 | Standard |
| V1600GS-F | 1 | Fiber uplink |
| V1600GS-ZF | 1 | Zero-touch |
| V1600GS-O32 | 1 | Built-in 1:32 splitter |
| V1600GS-WB | 1 | WDM backhaul |

### VSOL GPON OLTs (2 PON Ports)
| Model | PON Ports | Notes |
|-------|-----------|-------|
| V1600GT | 2 | Standard |
| V1600GT-2F | 2 | Dual fiber uplink |

### VSOL GPON OLTs (4 PON Ports)
| Model | PON Ports | Notes |
|-------|-----------|-------|
| V1600G0 | 4 | Standard |
| V1600G0-B | 4 | Basic |
| V1600G0-R | 4 | Rack mount |
| V1601G04 | 4 | G.984 compliant |
| V1601E04 | 4 | EPON/GPON Combo |

### VSOL GPON OLTs (8 PON Ports)
| Model | PON Ports | Notes |
|-------|-----------|-------|
| V1600G1 | 8 | Standard |
| V1600G1-B | 8 | Basic |
| V1600G1-R | 8 | Rack mount |
| V1600G1-A | 8 | Advanced |
| V1600G1WEO | 8 | Outdoor |
| V1600G1WEO-B | 8 | Outdoor IP65 rated |

### VSOL GPON OLTs (16 PON Ports)
| Model | PON Ports | Notes |
|-------|-----------|-------|
| V1600G2 | 16 | Standard |
| V1600G2-B | 16 | Basic |
| V1600G2-R | 16 | Rack mount |
| V1600G2-A | 16 | Advanced |

### VSOL EPON OLTs (1-2 PON Ports)
| Model | PON Ports | Notes |
|-------|-----------|-------|
| V1600DS | 1 | Single PON |
| V1600D2 | 2 | Standard |
| V1600D2-L | 2 | L2 switching |
| V1601E02 | 2 | EPON/GPON |
| V1601E02-DP | 2 | Dual power |

### VSOL EPON OLTs (4 PON Ports)
| Model | PON Ports | Notes |
|-------|-----------|-------|
| V1600D4 | 4 | Standard |
| V1600D4-L | 4 | L2 switching |
| V1600D4-DP | 4 | Dual power |
| V1600D-MINI | 4 | Compact design |
| V1601E04-DP | 4 | Dual power |
| V1601E04-BT | 4 | Battery backup |

### VSOL EPON OLTs (8 PON Ports)
| Model | PON Ports | Notes |
|-------|-----------|-------|
| V1600D8 | 8 | Standard |
| V1600D8-L | 8 | L2 switching |
| V1600D8-R | 8 | Rack mount |

### VSOL EPON OLTs (16 PON Ports)
| Model | PON Ports | Notes |
|-------|-----------|-------|
| V1600D16 | 16 | Standard |
| V1600D16-L | 16 | L2 switching |

### VSOL 10G-PON OLTs (XGS-PON/XG-PON)
| Model | PON Ports | Notes |
|-------|-----------|-------|
| V1600XG02 | 2 | 10G-PON |
| V1600XG02-W | 2 | 10G-PON WiFi |
| V1600XG04 | 4 | 10G-PON |

### VSOL P Series (Pizza Box)
| Model | PON Ports | Notes |
|-------|-----------|-------|
| V1600P1 | 1 | Pizza box form factor |
| V1600P2 | 2 | Pizza box form factor |
| V1600P4 | 4 | Pizza box form factor |
| V1600P8 | 8 | Pizza box form factor |

> **Note:** Custom OLT models can be added using the "Other" option with manual PON port configuration.

## License Plans

| Feature | Trial (7 Days) | Professional |
|---------|----------------|--------------|
| OLTs | 2 | 5+ |
| ONUs | 50 | 1000+ |
| Users | 2 | 10+ |
| Traffic Monitoring | Basic | Full |
| WhatsApp Alerts | - | Yes |
| Splitter Simulator | - | Yes |
| Priority Support | - | Yes |

Contact your vendor to upgrade after trial expires.

## Tech Stack

| Component | Technology |
|-----------|------------|
| **Backend** | Python FastAPI, SQLAlchemy, Paramiko, pysnmp |
| **Frontend** | React 18, Tailwind CSS |
| **Database** | SQLite |
| **Web Server** | Nginx |
| **Deployment** | Systemd service |

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
- `GET /api/olts/{id}/ports` - Get port information

### ONUs
- `GET /api/onus` - List all ONUs (supports filters)
- `GET /api/onus/search?q=query` - Search ONUs
- `GET /api/onus/{id}` - Get specific ONU
- `PUT /api/onus/{id}` - Update ONU
- `DELETE /api/onus/{id}` - Delete ONU
- `POST /api/onus/{id}/image` - Upload image
- `DELETE /api/onus/{id}/image` - Delete image
- `POST /api/onus/{id}/reboot` - Reboot ONU

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
- `GET /api/traffic/history/olt/{id}` - OLT traffic history
- `GET /api/traffic/history/onu/{id}` - ONU traffic history
- `GET /api/traffic/history/pon/{olt_id}/{port}` - PON port traffic history

### License & Updates
- `GET /api/license` - Get license information
- `GET /api/update-check` - Check for updates
- `POST /api/update/download` - Download update
- `POST /api/update/install` - Install update

## Configuration

Settings can be modified via the web interface under Settings page:

| Setting | Description | Default |
|---------|-------------|---------|
| System Name | Display name for the system | OLT Manager |
| Refresh Interval | Dashboard auto-refresh (seconds) | 30 |
| Polling Interval | OLT polling interval (seconds) | 60 |
| WhatsApp Enabled | Enable WhatsApp notifications | Off |
| WhatsApp Recipients | Phone numbers for alerts | - |
| SNMP Trap Port | Port for SNMP trap receiver | 162 |

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
user.password_hash = get_password_hash('admin123')
db.commit()
print('Password reset to: admin123')
"
```

## Security Notes

- Change default admin password immediately
- Use HTTPS in production (configure nginx with SSL)
- Restrict network access to management interface
- OLT credentials are stored encrypted in the database

## Screenshots

After installation, access the dashboard at `http://YOUR_SERVER_IP`

- **Dashboard**: Overview of all OLTs and ONUs with statistics
- **OLT List**: Manage your fiber network equipment
- **ONU Details**: View optical power, distance, traffic graphs
- **Live Traffic**: Real-time bandwidth monitoring
- **Settings**: Configure system and notifications

## Support

For issues and feature requests:
- GitHub: https://github.com/mmdelhajj/OLT-MANAGER/issues
- Contact your vendor for license upgrades

## License

Commercial License - Contact vendor for pricing

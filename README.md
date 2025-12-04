# EPON OLT/ONU Management Dashboard

A web-based dashboard for managing VSOL EPON OLTs and ONUs. Designed for ISPs to monitor and manage their fiber network equipment.

## Features

- **Dashboard Overview**: Total OLTs, ONUs, online/offline counts
- **OLT Management**: Add, edit, delete OLTs with SSH credentials
- **ONU Monitoring**: View all ONUs with MAC, customer name, status
- **Search**: Find customers by name or MAC address
- **Auto-Polling**: Automatic polling every 5 minutes
- **Manual Poll**: Trigger immediate poll for any OLT

## Supported Equipment

- VSOL V1600D8 (8 PON ports)
- VSOL V1601E04 (4 PON ports)
- Other VSOL EPON OLTs with similar CLI

## Tech Stack

- **Backend**: Python FastAPI, SQLAlchemy, Paramiko
- **Frontend**: React, Tailwind CSS
- **Database**: SQLite (default) or PostgreSQL
- **Deployment**: Docker & Docker Compose

## Quick Start

### Using Docker Compose (Recommended)

1. Clone or copy the project:
```bash
cd /path/to/olt-manager
```

2. Start the containers:
```bash
docker-compose up -d --build
```

3. Access the dashboard:
- Frontend: http://localhost
- API: http://localhost:8000

4. Add your first OLT through the web interface

### Network Configuration

The backend container needs to reach your OLTs via SSH. Options:

**Option 1: Bridge Network (Default)**
- Works if Docker host can reach OLTs
- OLT IPs must be routable from the Docker network

**Option 2: Host Network**
Uncomment in `docker-compose.yml`:
```yaml
backend:
  network_mode: host
```

### Manual Installation (Development)

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
python main.py
```

**Frontend:**
```bash
cd frontend
npm install
npm start
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

### ONUs
- `GET /api/onus` - List all ONUs (supports filters)
- `GET /api/olts/{id}/onus` - List ONUs for specific OLT
- `GET /api/onus/search?q=query` - Search by name/MAC
- `DELETE /api/onus/{id}` - Delete ONU record

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| DATABASE_URL | sqlite:///./olt_manager.db | Database connection string |
| POLL_INTERVAL | 300 | Polling interval in seconds |
| SSH_TIMEOUT | 30 | SSH connection timeout |
| SSH_PORT | 22 | Default SSH port |

## OLT CLI Commands Used

The system connects via SSH and runs:
- `show running-config` - Get ONU MAC bindings and descriptions

Expected config format:
```
interface epon 0/1
confirm onu mac 4c:d7:c8:f9:91:00 onuid 1
onu 1 description CUSTOMER-NAME
exit
```

## Troubleshooting

### OLT shows offline
- Check network connectivity from Docker host to OLT
- Verify SSH credentials
- Check OLT IP address
- View error in dashboard (hover over error indicator)

### ONUs not appearing
- Verify OLT config format matches expected patterns
- Check poll logs in database
- Try manual poll and check response

### SSH Connection Issues
- Ensure OLT allows SSH connections
- Check firewall rules
- Verify SSH is enabled on OLT

## Project Structure

```
olt-manager/
├── backend/
│   ├── main.py           # FastAPI app & endpoints
│   ├── models.py         # Database models
│   ├── schemas.py        # Pydantic schemas
│   ├── olt_connector.py  # SSH connection & parsing
│   ├── config.py         # Configuration
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.js        # Main React component
│   │   ├── api.js        # API client
│   │   └── index.js      # Entry point
│   ├── public/
│   │   └── index.html
│   ├── nginx.conf
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
└── README.md
```

## Security Notes

- OLT passwords are stored in the database (consider encrypting in production)
- The API has no authentication (add auth for production deployment)
- Use HTTPS in production (configure nginx with SSL certificates)

## License

MIT License

"""
Cloudflare Tunnel Manager for OLT Manager
Enables remote access via subdomains like abc123.olt.mes.net.lb
"""
import os
import json
import subprocess
import logging
import random
import string
import requests
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Cloudflare Configuration
CF_API_TOKEN = os.getenv("CF_API_TOKEN", "9HRE1aLLwTmZtg_tlRzytFvW2pW7hO4mAPeGjs1Y")
CF_ZONE_ID = os.getenv("CF_ZONE_ID", "8c536429361fea2b7421d8cb72db8725")
CF_ACCOUNT_ID = os.getenv("CF_ACCOUNT_ID", "")  # Will be fetched automatically
CF_DOMAIN = "mes.net.lb"  # Base domain - subdomain will be olt-{id}.mes.net.lb
CF_API_BASE = "https://api.cloudflare.com/client/v4"

# Tunnel configuration paths
TUNNEL_CONFIG_DIR = Path("/etc/olt-manager/tunnel")
TUNNEL_CONFIG_FILE = TUNNEL_CONFIG_DIR / "config.yml"
TUNNEL_CREDS_FILE = TUNNEL_CONFIG_DIR / "credentials.json"
TUNNEL_STATUS_FILE = TUNNEL_CONFIG_DIR / "status.json"

# Service name
TUNNEL_SERVICE = "cloudflared"


class TunnelManager:
    def __init__(self):
        self.tunnel_id: Optional[str] = None
        self.subdomain: Optional[str] = None
        self.tunnel_url: Optional[str] = None
        self.is_running: bool = False
        self.account_id: Optional[str] = None
        self._load_status()
        self._get_account_id()

    def _get_headers(self) -> Dict[str, str]:
        """Get Cloudflare API headers"""
        return {
            "Authorization": f"Bearer {CF_API_TOKEN}",
            "Content-Type": "application/json"
        }

    def _get_account_id(self):
        """Get Cloudflare account ID"""
        if self.account_id:
            return self.account_id

        try:
            # Get account ID from zone info
            resp = requests.get(
                f"{CF_API_BASE}/zones/{CF_ZONE_ID}",
                headers=self._get_headers(),
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                self.account_id = data.get("result", {}).get("account", {}).get("id")
                logger.info(f"Got Cloudflare account ID: {self.account_id}")
        except Exception as e:
            logger.error(f"Failed to get account ID: {e}")

        return self.account_id

    def _load_status(self):
        """Load tunnel status from file"""
        try:
            if TUNNEL_STATUS_FILE.exists():
                with open(TUNNEL_STATUS_FILE, 'r') as f:
                    status = json.load(f)
                    self.tunnel_id = status.get('tunnel_id')
                    self.subdomain = status.get('subdomain')
                    self.tunnel_url = status.get('tunnel_url')
                    self.is_running = self._check_service_running()
        except Exception as e:
            logger.warning(f"Failed to load tunnel status: {e}")

    def _save_status(self):
        """Save tunnel status to file"""
        try:
            TUNNEL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(TUNNEL_STATUS_FILE, 'w') as f:
                json.dump({
                    'tunnel_id': self.tunnel_id,
                    'subdomain': self.subdomain,
                    'tunnel_url': self.tunnel_url
                }, f, indent=2)
            os.chmod(TUNNEL_STATUS_FILE, 0o600)
        except Exception as e:
            logger.error(f"Failed to save tunnel status: {e}")

    def _generate_subdomain(self) -> str:
        """Generate unique subdomain in format olt-{id}"""
        # Read hardware ID for consistent subdomain
        hw_id_file = Path('/etc/olt-manager/hardware.id')
        if hw_id_file.exists():
            hw_id = hw_id_file.read_text().strip()
            # Use last 6 chars of hardware ID with olt- prefix
            suffix = hw_id.replace('-', '').lower()[-6:]
            return f"olt-{suffix}"

        # Fallback to random
        suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        return f"olt-{suffix}"

    def _check_service_running(self) -> bool:
        """Check if cloudflared service is running"""
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', 'cloudflared'],
                capture_output=True, text=True
            )
            return result.stdout.strip() == 'active'
        except:
            return False

    def _install_cloudflared(self) -> bool:
        """Install cloudflared if not present"""
        try:
            # Check if already installed
            result = subprocess.run(['which', 'cloudflared'], capture_output=True)
            if result.returncode == 0:
                logger.info("cloudflared already installed")
                return True

            logger.info("Installing cloudflared...")

            # Download and install cloudflared
            arch = subprocess.run(['uname', '-m'], capture_output=True, text=True).stdout.strip()
            if arch == 'x86_64':
                arch = 'amd64'
            elif arch == 'aarch64':
                arch = 'arm64'

            download_url = f"https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-{arch}.deb"

            subprocess.run(['wget', '-q', '-O', '/tmp/cloudflared.deb', download_url], check=True)
            subprocess.run(['dpkg', '-i', '/tmp/cloudflared.deb'], check=True)
            subprocess.run(['rm', '/tmp/cloudflared.deb'])

            logger.info("cloudflared installed successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to install cloudflared: {e}")
            return False

    def _create_tunnel(self) -> Optional[str]:
        """Create Cloudflare tunnel via API"""
        if not self.account_id:
            logger.error("No account ID available")
            return None

        try:
            # Generate tunnel name
            tunnel_name = f"olt-{self._generate_subdomain()}"

            # Create tunnel via API
            resp = requests.post(
                f"{CF_API_BASE}/accounts/{self.account_id}/cfd_tunnel",
                headers=self._get_headers(),
                json={
                    "name": tunnel_name,
                    "config_src": "cloudflare"
                },
                timeout=30
            )

            if resp.status_code in [200, 201]:
                data = resp.json()
                tunnel = data.get("result", {})
                self.tunnel_id = tunnel.get("id")
                logger.info(f"Created tunnel: {self.tunnel_id}")
                return self.tunnel_id
            else:
                logger.error(f"Failed to create tunnel: {resp.text}")
                return None

        except Exception as e:
            logger.error(f"Error creating tunnel: {e}")
            return None

    def _create_dns_record(self, subdomain: str) -> bool:
        """Create DNS record for tunnel"""
        try:
            full_domain = f"{subdomain}.{CF_DOMAIN}"
            tunnel_domain = f"{self.tunnel_id}.cfargotunnel.com"

            # Check if record exists
            resp = requests.get(
                f"{CF_API_BASE}/zones/{CF_ZONE_ID}/dns_records",
                headers=self._get_headers(),
                params={"name": full_domain, "type": "CNAME"},
                timeout=10
            )

            if resp.status_code == 200:
                records = resp.json().get("result", [])
                if records:
                    # Update existing record
                    record_id = records[0]["id"]
                    resp = requests.put(
                        f"{CF_API_BASE}/zones/{CF_ZONE_ID}/dns_records/{record_id}",
                        headers=self._get_headers(),
                        json={
                            "type": "CNAME",
                            "name": full_domain,
                            "content": tunnel_domain,
                            "proxied": True
                        },
                        timeout=10
                    )
                else:
                    # Create new record
                    resp = requests.post(
                        f"{CF_API_BASE}/zones/{CF_ZONE_ID}/dns_records",
                        headers=self._get_headers(),
                        json={
                            "type": "CNAME",
                            "name": full_domain,
                            "content": tunnel_domain,
                            "proxied": True
                        },
                        timeout=10
                    )

            if resp.status_code in [200, 201]:
                logger.info(f"DNS record created: {full_domain} -> {tunnel_domain}")
                return True
            else:
                logger.error(f"Failed to create DNS record: {resp.text}")
                return False

        except Exception as e:
            logger.error(f"Error creating DNS record: {e}")
            return False

    def _configure_tunnel(self) -> bool:
        """Configure tunnel with config file"""
        try:
            TUNNEL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

            # Get tunnel credentials/token
            if not self.account_id or not self.tunnel_id:
                return False

            # Get tunnel token
            resp = requests.get(
                f"{CF_API_BASE}/accounts/{self.account_id}/cfd_tunnel/{self.tunnel_id}/token",
                headers=self._get_headers(),
                timeout=10
            )

            if resp.status_code != 200:
                logger.error(f"Failed to get tunnel token: {resp.text}")
                return False

            tunnel_token = resp.json().get("result", "")

            # Save token to file
            token_file = TUNNEL_CONFIG_DIR / "token"
            with open(token_file, 'w') as f:
                f.write(tunnel_token)
            os.chmod(token_file, 0o600)

            # Configure tunnel ingress via API
            config = {
                "config": {
                    "ingress": [
                        {
                            "hostname": f"{self.subdomain}.{CF_DOMAIN}",
                            "service": "http://localhost:80"
                        },
                        {
                            "service": "http_status:404"
                        }
                    ]
                }
            }

            resp = requests.put(
                f"{CF_API_BASE}/accounts/{self.account_id}/cfd_tunnel/{self.tunnel_id}/configurations",
                headers=self._get_headers(),
                json=config,
                timeout=10
            )

            if resp.status_code not in [200, 201]:
                logger.warning(f"Failed to configure tunnel ingress: {resp.text}")

            # Create systemd service
            service_content = f"""[Unit]
Description=Cloudflare Tunnel for OLT Manager
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
ExecStart=/usr/bin/cloudflared tunnel --no-autoupdate run --token {tunnel_token}
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
"""

            service_file = Path("/etc/systemd/system/cloudflared.service")
            with open(service_file, 'w') as f:
                f.write(service_content)

            # Reload systemd
            subprocess.run(['systemctl', 'daemon-reload'], check=True)

            logger.info("Tunnel configured successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to configure tunnel: {e}")
            return False

    def _start_service(self) -> bool:
        """Start cloudflared service"""
        try:
            subprocess.run(['systemctl', 'enable', 'cloudflared'], check=True)
            subprocess.run(['systemctl', 'restart', 'cloudflared'], check=True)

            # Wait a bit and check status
            import time
            time.sleep(3)

            self.is_running = self._check_service_running()
            return self.is_running

        except Exception as e:
            logger.error(f"Failed to start cloudflared: {e}")
            return False

    def _stop_service(self) -> bool:
        """Stop cloudflared service"""
        try:
            subprocess.run(['systemctl', 'stop', 'cloudflared'])
            subprocess.run(['systemctl', 'disable', 'cloudflared'])
            self.is_running = False
            return True
        except Exception as e:
            logger.error(f"Failed to stop cloudflared: {e}")
            return False

    def enable_tunnel(self) -> Dict[str, Any]:
        """Enable remote access tunnel"""
        try:
            # Check if already enabled
            if self.tunnel_id and self.is_running:
                return {
                    'success': True,
                    'message': 'Tunnel already running',
                    'url': self.tunnel_url,
                    'subdomain': self.subdomain
                }

            # Step 1: Install cloudflared
            if not self._install_cloudflared():
                return {'success': False, 'error': 'Failed to install cloudflared'}

            # Step 2: Generate subdomain if not set
            if not self.subdomain:
                self.subdomain = self._generate_subdomain()

            # Step 3: Create tunnel if not exists
            if not self.tunnel_id:
                if not self._create_tunnel():
                    return {'success': False, 'error': 'Failed to create Cloudflare tunnel'}

            # Step 4: Create DNS record
            if not self._create_dns_record(self.subdomain):
                return {'success': False, 'error': 'Failed to create DNS record'}

            # Step 5: Configure tunnel
            if not self._configure_tunnel():
                return {'success': False, 'error': 'Failed to configure tunnel'}

            # Step 6: Start service
            if not self._start_service():
                return {'success': False, 'error': 'Failed to start tunnel service'}

            # Save status
            self.tunnel_url = f"https://{self.subdomain}.{CF_DOMAIN}"
            self._save_status()

            logger.info(f"Tunnel enabled: {self.tunnel_url}")

            return {
                'success': True,
                'message': 'Remote access enabled',
                'url': self.tunnel_url,
                'subdomain': self.subdomain
            }

        except Exception as e:
            logger.error(f"Failed to enable tunnel: {e}")
            return {'success': False, 'error': str(e)}

    def disable_tunnel(self) -> Dict[str, Any]:
        """Disable remote access tunnel"""
        try:
            self._stop_service()

            # Optionally delete DNS record (keep tunnel for re-enable)

            self.is_running = False
            self._save_status()

            return {
                'success': True,
                'message': 'Remote access disabled'
            }

        except Exception as e:
            logger.error(f"Failed to disable tunnel: {e}")
            return {'success': False, 'error': str(e)}

    def get_status(self) -> Dict[str, Any]:
        """Get tunnel status"""
        self.is_running = self._check_service_running()

        return {
            'enabled': self.tunnel_id is not None,
            'running': self.is_running,
            'url': self.tunnel_url if self.is_running else None,
            'subdomain': self.subdomain,
            'tunnel_id': self.tunnel_id
        }

    def delete_tunnel(self) -> Dict[str, Any]:
        """Delete tunnel completely"""
        try:
            # Stop service first
            self._stop_service()

            # Delete tunnel via API
            if self.tunnel_id and self.account_id:
                resp = requests.delete(
                    f"{CF_API_BASE}/accounts/{self.account_id}/cfd_tunnel/{self.tunnel_id}",
                    headers=self._get_headers(),
                    timeout=10
                )
                if resp.status_code in [200, 204]:
                    logger.info(f"Tunnel {self.tunnel_id} deleted")

            # Clean up local files
            if TUNNEL_STATUS_FILE.exists():
                TUNNEL_STATUS_FILE.unlink()

            self.tunnel_id = None
            self.subdomain = None
            self.tunnel_url = None

            return {'success': True, 'message': 'Tunnel deleted'}

        except Exception as e:
            logger.error(f"Failed to delete tunnel: {e}")
            return {'success': False, 'error': str(e)}


# Global instance
tunnel_manager = TunnelManager()

"""
License Manager for OLT Manager
Online validation system with hardware fingerprint
"""
import os
import hashlib
import uuid
import platform
import socket
import requests
import json
import logging
import asyncio
import sys
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

# Your license server URL (change this to your domain)
LICENSE_SERVER_URL = os.getenv("LICENSE_SERVER_URL", "http://lic.proxpanel.com")
LICENSE_CHECK_ENDPOINT = "/api/validate"
LICENSE_CACHE_FILE = Path("/var/lib/olt-manager/.license_cache")

# Grace period if server unreachable (days)
OFFLINE_GRACE_DAYS = 7

# How often to check license (seconds) - 5 minutes
LICENSE_CHECK_INTERVAL = 300

# Current software version - read from version file if exists
def get_version_file_path():
    """Get version file path for different install locations"""
    paths = [
        Path("/opt/olt-manager/backend/VERSION"),
        Path("/root/olt-manager/backend/VERSION"),
        Path(__file__).parent / "VERSION"
    ]
    for p in paths:
        if p.exists():
            return p
    return paths[0]  # Default to /opt path

VERSION_FILE = get_version_file_path()

def get_software_version():
    """Get software version from file or default"""
    try:
        version_file = get_version_file_path()
        if version_file.exists():
            return version_file.read_text().strip()
    except:
        pass
    return "1.0.0"

SOFTWARE_VERSION = get_software_version()


class LicenseError(Exception):
    """License validation error"""
    pass


class LicenseManager:
    def __init__(self):
        self.license_key: Optional[str] = None
        self.license_data: Optional[Dict[str, Any]] = None
        self.hardware_id: str = self._generate_hardware_id()
        self.last_check: Optional[datetime] = None
        self.is_valid: bool = False
        self.error_message: Optional[str] = None
        self.update_info: Optional[Dict[str, Any]] = None  # Store update info from server

    def _generate_hardware_id(self) -> str:
        """Generate unique hardware fingerprint - uses install script's ID if available"""
        # First, try to read hardware ID saved by install script
        hardware_id_file = Path('/etc/olt-manager/hardware.id')
        try:
            if hardware_id_file.exists():
                saved_id = hardware_id_file.read_text().strip()
                if saved_id:
                    logger.info(f"Using hardware ID from install: {saved_id}")
                    return saved_id
        except Exception as e:
            logger.warning(f"Could not read hardware ID file: {e}")

        # Fallback: Generate hardware ID same way as install script
        components = []

        # Get machine ID (Linux)
        try:
            if os.path.exists('/etc/machine-id'):
                with open('/etc/machine-id', 'r') as f:
                    components.append(f.read().strip())
        except:
            pass

        # Get CPU info
        try:
            if os.path.exists('/proc/cpuinfo'):
                with open('/proc/cpuinfo', 'r') as f:
                    for line in f:
                        if 'Serial' in line or 'model name' in line:
                            import subprocess
                            result = subprocess.run(['md5sum'], input=line.strip().encode(), capture_output=True)
                            components.append(result.stdout.decode().split()[0])
                            break
        except:
            pass

        # Get MAC address
        try:
            import subprocess
            result = subprocess.run(['ip', 'link', 'show'], capture_output=True, text=True)
            for line in result.stdout.split('\n'):
                if 'link/ether' in line:
                    mac = line.split()[1].replace(':', '')
                    components.append(mac)
                    break
        except:
            pass

        # Generate hash same as install script
        fingerprint = ''.join(components)
        import subprocess
        result = subprocess.run(['md5sum'], input=fingerprint.encode(), capture_output=True)
        full_hash = result.stdout.decode().split()[0]

        # Format like install script: OLT-XXXXXXXX-XXXXXXXX-XXXXXXXX
        hardware_id = f"OLT-{full_hash[:8]}-{full_hash[8:16]}-{full_hash[16:24]}".upper()
        logger.info(f"Generated hardware ID: {hardware_id}")
        return hardware_id

    def _load_cached_license(self) -> bool:
        """Load license from cache file"""
        try:
            if LICENSE_CACHE_FILE.exists():
                with open(LICENSE_CACHE_FILE, 'r') as f:
                    cache = json.load(f)

                self.license_key = cache.get('license_key')
                self.license_data = cache.get('license_data')
                self.last_check = datetime.fromisoformat(cache.get('last_check', '2000-01-01'))

                # Check if cache is within grace period
                if datetime.now() - self.last_check < timedelta(days=OFFLINE_GRACE_DAYS):
                    return True
        except Exception as e:
            logger.warning(f"Failed to load license cache: {e}")
        return False

    def _save_license_cache(self):
        """Save license to cache file"""
        try:
            LICENSE_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(LICENSE_CACHE_FILE, 'w') as f:
                json.dump({
                    'license_key': self.license_key,
                    'license_data': self.license_data,
                    'last_check': datetime.now().isoformat()
                }, f)
            # Secure the file
            os.chmod(LICENSE_CACHE_FILE, 0o600)
        except Exception as e:
            logger.warning(f"Failed to save license cache: {e}")

    def _clear_cache(self):
        """Clear license cache when license is invalid"""
        try:
            if LICENSE_CACHE_FILE.exists():
                LICENSE_CACHE_FILE.unlink()
        except Exception as e:
            logger.warning(f"Failed to clear license cache: {e}")

    def _validate_online(self, license_key: str) -> Dict[str, Any]:
        """Validate license with online server"""
        try:
            response = requests.post(
                f"{LICENSE_SERVER_URL}{LICENSE_CHECK_ENDPOINT}",
                json={
                    'license_key': license_key,
                    'hardware_id': self.hardware_id,
                    'product': 'olt-manager',
                    'version': SOFTWARE_VERSION
                },
                timeout=10,
                headers={'Content-Type': 'application/json'}
            )

            if response.status_code == 200:
                data = response.json()
                # Extract and store update info if available
                if 'update' in data:
                    self.update_info = data['update']
                    logger.info(f"Update available: v{data['update'].get('latest_version')}")
                else:
                    self.update_info = None
                return data
            elif response.status_code == 403:
                error_msg = response.json().get('error', 'License invalid or revoked')
                raise LicenseError(error_msg)
            elif response.status_code == 409:
                raise LicenseError("License is already activated on another device")
            else:
                raise LicenseError(f"License server error: {response.status_code}")

        except requests.exceptions.Timeout:
            raise LicenseError("License server timeout - check internet connection")
        except requests.exceptions.ConnectionError:
            raise LicenseError("Cannot connect to license server")

    def validate(self, license_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Validate license key
        Returns license data if valid, raises LicenseError if not
        """
        # Try to load from environment or parameter
        key = license_key or os.getenv('OLT_LICENSE_KEY')

        if not key:
            # Check for license file
            license_file = Path('/etc/olt-manager/license.key')
            if license_file.exists():
                key = license_file.read_text().strip()

        if not key:
            self.is_valid = False
            self.error_message = "No license key found"
            raise LicenseError("No license key found. Set OLT_LICENSE_KEY environment variable or create /etc/olt-manager/license.key")

        self.license_key = key

        # Try online validation
        try:
            self.license_data = self._validate_online(key)
            self.last_check = datetime.now()
            self.is_valid = True
            self.error_message = None
            self._save_license_cache()

            logger.info(f"License validated: {self.license_data.get('customer_name', 'Unknown')}")
            return self.license_data

        except LicenseError as e:
            # License is explicitly invalid (suspended, revoked, expired)
            error_str = str(e)
            if 'suspended' in error_str.lower() or 'revoked' in error_str.lower() or 'expired' in error_str.lower():
                self.is_valid = False
                self.error_message = error_str
                self._clear_cache()  # Clear cache so it can't be used offline
                raise
            else:
                # Connection error - try cached license
                logger.warning(f"Online validation failed: {e}")
                if self._load_cached_license():
                    logger.info("Using cached license (offline mode)")
                    self.is_valid = True
                    return self.license_data
                else:
                    self.is_valid = False
                    self.error_message = str(e)
                    raise LicenseError("Cannot validate license - server unreachable and no valid cache")

        except Exception as e:
            # Connection error - try cached license
            logger.warning(f"Online validation failed: {e}")

            if self._load_cached_license():
                logger.info("Using cached license (offline mode)")
                self.is_valid = True
                return self.license_data
            else:
                self.is_valid = False
                self.error_message = str(e)
                raise LicenseError("Cannot validate license - server unreachable and no valid cache")

    def check_license_periodic(self) -> bool:
        """
        Periodic license check - called by background task
        Returns True if license is still valid, False if not
        """
        try:
            self.validate()
            return True
        except LicenseError as e:
            logger.error(f"License check failed: {e}")
            self.is_valid = False
            self.error_message = str(e)
            return False

    def get_license_info(self) -> Dict[str, Any]:
        """Get current license information"""
        if not self.license_data:
            return {
                'valid': False,
                'message': 'No license loaded',
                'error_message': self.error_message
            }

        return {
            'valid': self.is_valid,
            'customer_name': self.license_data.get('customer_name', 'Unknown'),
            'max_olts': self.license_data.get('max_olts', 1),
            'max_onus': self.license_data.get('max_onus', 100),
            'max_users': self.license_data.get('max_users', 5),
            'expires_at': self.license_data.get('expires_at'),
            'features': self.license_data.get('features', []),
            'license_type': self.license_data.get('license_type', 'standard'),
            'package_type': self.license_data.get('package_type', 'standard'),
            'hardware_id': self.hardware_id,
            'error_message': self.error_message
        }

    def check_limit(self, resource: str, current_count: int) -> bool:
        """Check if resource limit is exceeded"""
        if not self.license_data:
            return False

        limits = {
            'olts': self.license_data.get('max_olts', 1),
            'onus': self.license_data.get('max_onus', 100),
            'users': self.license_data.get('max_users', 5)
        }

        max_allowed = limits.get(resource, float('inf'))
        return current_count < max_allowed

    def has_feature(self, feature: str) -> bool:
        """Check if license includes a feature"""
        if not self.license_data:
            return False

        features = self.license_data.get('features', [])
        return feature in features or 'all' in features


# Global instance
license_manager = LicenseManager()


def require_license(func):
    """Decorator to require valid license"""
    def wrapper(*args, **kwargs):
        if not license_manager.is_valid:
            raise LicenseError(license_manager.error_message or "License not validated")
        return func(*args, **kwargs)
    return wrapper


# Development mode - skip license check
DEV_MODE = os.getenv('OLT_DEV_MODE', 'false').lower() == 'true'


def validate_license_on_startup():
    """Called on application startup"""
    if DEV_MODE:
        logger.warning("⚠️ Running in DEVELOPMENT MODE - license check skipped")
        license_manager.license_data = {
            'customer_name': 'Development',
            'max_olts': 999,
            'max_onus': 99999,
            'features': ['all']
        }
        license_manager.is_valid = True
        return True

    try:
        license_manager.validate()
        return True
    except LicenseError as e:
        logger.error(f"❌ LICENSE ERROR: {e}")
        return False


async def license_check_loop():
    """Background task to periodically check license validity"""
    if DEV_MODE:
        return  # Don't run in dev mode

    logger.info(f"Started license check loop (interval: {LICENSE_CHECK_INTERVAL}s)")

    while True:
        await asyncio.sleep(LICENSE_CHECK_INTERVAL)

        try:
            if not license_manager.check_license_periodic():
                logger.warning("=" * 50)
                logger.warning("LICENSE CHECK FAILED - READ-ONLY MODE")
                logger.warning(f"Reason: {license_manager.error_message}")
                logger.warning("=" * 50)
            else:
                logger.debug("Periodic license check: OK")

        except Exception as e:
            logger.error(f"Error in license check loop: {e}")

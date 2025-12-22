"""Configuration settings for OLT Manager"""
import os
import hashlib
import base64
import secrets

# Security: Salt file for encryption key derivation
ENCRYPTION_SALT_FILE = "/etc/olt-manager/encryption.salt"
PBKDF2_ITERATIONS = 100000  # High iteration count for security


def _get_or_create_salt() -> bytes:
    """Get or create a persistent random salt for key derivation"""
    try:
        if os.path.exists(ENCRYPTION_SALT_FILE):
            with open(ENCRYPTION_SALT_FILE, 'rb') as f:
                salt = f.read()
                if len(salt) >= 16:
                    return salt
    except Exception:
        pass

    # Generate new random salt
    salt = secrets.token_bytes(32)
    try:
        os.makedirs(os.path.dirname(ENCRYPTION_SALT_FILE), exist_ok=True)
        with open(ENCRYPTION_SALT_FILE, 'wb') as f:
            f.write(salt)
        os.chmod(ENCRYPTION_SALT_FILE, 0o600)  # Only root can read
    except Exception:
        pass  # If we can't save, still use the generated salt

    return salt


def _get_hardware_id() -> str:
    """Get hardware ID from file or machine-id"""
    hardware_id_file = "/etc/olt-manager/hardware.id"
    try:
        if os.path.exists(hardware_id_file):
            with open(hardware_id_file, 'r') as f:
                return f.read().strip()
        else:
            # Fallback: use machine-id
            with open('/etc/machine-id', 'r') as f:
                return f.read().strip()
    except Exception:
        return secrets.token_hex(16)


def get_encryption_key():
    """Generate encryption key using PBKDF2 with hardware ID and random salt"""
    hardware_id = _get_hardware_id()

    # Get persistent salt
    salt = _get_or_create_salt()

    # Use PBKDF2 for secure key derivation (much stronger than simple SHA256)
    key = hashlib.pbkdf2_hmac(
        'sha256',
        hardware_id.encode(),
        salt,
        PBKDF2_ITERATIONS,
        dklen=32
    )
    return key


def get_legacy_encryption_key():
    """Get the old encryption key (simple SHA256) for migration"""
    hardware_id = _get_hardware_id()
    return hashlib.sha256(hardware_id.encode()).digest()

# Encryption key for sensitive data (OLT passwords, etc.)
ENCRYPTION_KEY = get_encryption_key()

import logging
_config_logger = logging.getLogger(__name__)


def encrypt_sensitive(plaintext: str) -> str:
    """Encrypt sensitive data using Fernet (AES-128-CBC)"""
    if not plaintext:
        return plaintext
    try:
        from cryptography.fernet import Fernet
        # Create Fernet key from hardware-based key
        key = base64.urlsafe_b64encode(ENCRYPTION_KEY)
        f = Fernet(key)
        encrypted = f.encrypt(plaintext.encode())
        return "ENC:" + encrypted.decode()
    except Exception as e:
        # Log the error - encryption should not fail silently
        _config_logger.error(f"[SECURITY] Encryption failed: {e}")
        # In production, raise an exception instead of returning plaintext
        raise ValueError("Encryption failed - cannot store sensitive data in plaintext")


def decrypt_sensitive(ciphertext: str) -> str:
    """Decrypt sensitive data - tries new key first, then legacy key for migration"""
    if not ciphertext:
        return ciphertext
    if not ciphertext.startswith("ENC:"):
        # Not encrypted - this is legacy data, log a warning
        _config_logger.warning("[SECURITY] Found unencrypted sensitive data - should be re-encrypted")
        return ciphertext

    from cryptography.fernet import Fernet
    encrypted_data = ciphertext[4:]  # Remove "ENC:" prefix

    # Try new PBKDF2 key first
    try:
        key = base64.urlsafe_b64encode(ENCRYPTION_KEY)
        f = Fernet(key)
        decrypted = f.decrypt(encrypted_data.encode())
        return decrypted.decode()
    except Exception:
        pass  # Try legacy key

    # Try legacy key (simple SHA256) for migration from old versions
    try:
        legacy_key = get_legacy_encryption_key()
        key = base64.urlsafe_b64encode(legacy_key)
        f = Fernet(key)
        decrypted = f.decrypt(encrypted_data.encode())
        _config_logger.info("[SECURITY] Decrypted with legacy key - data will be re-encrypted on next save")
        return decrypted.decode()
    except Exception as e:
        _config_logger.error(f"[SECURITY] Decryption failed with both keys: {e}")
        raise ValueError("Decryption failed - data may be corrupted or key changed")

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./olt_manager.db")

# Polling interval in seconds (1 minute)
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", 60))

# SSH connection settings
SSH_TIMEOUT = int(os.getenv("SSH_TIMEOUT", 30))
SSH_PORT = int(os.getenv("SSH_PORT", 22))

# Default OLT credentials (can be overridden per OLT)
DEFAULT_OLT_USERNAME = os.getenv("DEFAULT_OLT_USERNAME", "admin")
DEFAULT_OLT_PASSWORD = os.getenv("DEFAULT_OLT_PASSWORD", "admin")

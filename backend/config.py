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


def get_encryption_key():
    """Generate encryption key using PBKDF2 with hardware ID and random salt"""
    hardware_id_file = "/etc/olt-manager/hardware.id"
    try:
        if os.path.exists(hardware_id_file):
            with open(hardware_id_file, 'r') as f:
                hardware_id = f.read().strip()
        else:
            # Fallback: use machine-id
            with open('/etc/machine-id', 'r') as f:
                hardware_id = f.read().strip()
    except Exception:
        # If no hardware ID available, generate a persistent one
        hardware_id = secrets.token_hex(16)

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
    """Decrypt sensitive data"""
    if not ciphertext:
        return ciphertext
    if not ciphertext.startswith("ENC:"):
        # Not encrypted - this is legacy data, log a warning
        _config_logger.warning("[SECURITY] Found unencrypted sensitive data - should be re-encrypted")
        return ciphertext
    try:
        from cryptography.fernet import Fernet
        key = base64.urlsafe_b64encode(ENCRYPTION_KEY)
        f = Fernet(key)
        encrypted_data = ciphertext[4:]  # Remove "ENC:" prefix
        decrypted = f.decrypt(encrypted_data.encode())
        return decrypted.decode()
    except Exception as e:
        # Log the error
        _config_logger.error(f"[SECURITY] Decryption failed: {e}")
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

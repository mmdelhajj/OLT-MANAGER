"""Configuration settings for OLT Manager"""
import os
import hashlib
import base64

# Generate encryption key from hardware ID
def get_encryption_key():
    """Generate encryption key based on hardware ID for sensitive data"""
    hardware_id_file = "/etc/olt-manager/hardware.id"
    try:
        if os.path.exists(hardware_id_file):
            with open(hardware_id_file, 'r') as f:
                hardware_id = f.read().strip()
        else:
            # Fallback: use machine-id
            with open('/etc/machine-id', 'r') as f:
                hardware_id = f.read().strip()
    except:
        hardware_id = "OLT-DEFAULT-KEY"

    # Create a 32-byte key from hardware ID
    return hashlib.sha256(hardware_id.encode()).digest()

# Encryption key for sensitive data (OLT passwords, etc.)
ENCRYPTION_KEY = get_encryption_key()

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
    except Exception:
        # If encryption fails, return original (for backward compatibility)
        return plaintext

def decrypt_sensitive(ciphertext: str) -> str:
    """Decrypt sensitive data"""
    if not ciphertext:
        return ciphertext
    if not ciphertext.startswith("ENC:"):
        # Not encrypted, return as-is (backward compatibility)
        return ciphertext
    try:
        from cryptography.fernet import Fernet
        key = base64.urlsafe_b64encode(ENCRYPTION_KEY)
        f = Fernet(key)
        encrypted_data = ciphertext[4:]  # Remove "ENC:" prefix
        decrypted = f.decrypt(encrypted_data.encode())
        return decrypted.decode()
    except Exception:
        # If decryption fails, return original
        return ciphertext

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

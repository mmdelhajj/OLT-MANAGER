"""Configuration settings for OLT Manager"""
import os

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

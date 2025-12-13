#!/usr/bin/env python3
"""Script to set web credentials for OLT"""
import sys
import os

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import encrypt_sensitive
from models import SessionLocal, OLT

def set_credentials(ip: str, username: str, password: str):
    db = SessionLocal()
    try:
        olt = db.query(OLT).filter(OLT.ip_address == ip).first()
        if olt:
            olt.web_username = username
            olt.web_password = encrypt_sensitive(password)
            db.commit()
            print(f"Web credentials set for OLT {olt.name} ({ip})")
            print(f"  Username: {username}")
            print(f"  Password: {'*' * len(password)} (encrypted)")
            return True
        else:
            print(f"OLT with IP {ip} not found")
            return False
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python set_web_credentials.py <ip> <username> <password>")
        sys.exit(1)

    ip = sys.argv[1]
    username = sys.argv[2]
    password = sys.argv[3]

    success = set_credentials(ip, username, password)
    sys.exit(0 if success else 1)

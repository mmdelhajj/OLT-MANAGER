"""Seed script to add initial OLTs"""
import sys
from models import init_db, SessionLocal, OLT

# Your OLT configurations
OLTS = [
    {
        "name": "OLT-1",
        "ip_address": "10.10.10.1",
        "username": "admin",
        "password": "admin",  # Change this to your actual password
        "model": "V1601E04",
        "pon_ports": 4
    },
    {
        "name": "OLT-2",
        "ip_address": "10.10.20.1",
        "username": "admin",
        "password": "admin",  # Change this to your actual password
        "model": "V1601E04",
        "pon_ports": 4
    },
    {
        "name": "OLT-3",
        "ip_address": "10.10.30.1",
        "username": "admin",
        "password": "admin",  # Change this to your actual password
        "model": "V1600D8",
        "pon_ports": 8
    },
]


def seed_olts():
    """Add OLTs to database"""
    init_db()
    db = SessionLocal()

    try:
        for olt_data in OLTS:
            # Check if OLT already exists
            existing = db.query(OLT).filter(OLT.ip_address == olt_data["ip_address"]).first()
            if existing:
                print(f"OLT {olt_data['ip_address']} already exists, skipping...")
                continue

            olt = OLT(**olt_data)
            db.add(olt)
            print(f"Added OLT: {olt_data['name']} ({olt_data['ip_address']})")

        db.commit()
        print("\nDone! OLTs added successfully.")
        print("The background poller will connect to them automatically.")

    finally:
        db.close()


if __name__ == "__main__":
    seed_olts()

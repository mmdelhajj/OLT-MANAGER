#!/usr/bin/env python3
"""
Reset admin account - unlocks and resets password to 'admin'
Run this on the server to fix login issues
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import User, Base
import bcrypt

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "olt_manager.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

def reset_admin():
    """Reset admin account"""
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        # Find admin user
        admin = db.query(User).filter(User.username == "admin").first()

        if not admin:
            print("[!] Admin user not found, creating...")
            password_hash = bcrypt.hashpw("admin".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            admin = User(
                username="admin",
                password_hash=password_hash,
                role="admin",
                full_name="Administrator"
            )
            db.add(admin)
        else:
            print("[*] Resetting admin account...")
            # Reset password to 'admin'
            admin.password_hash = bcrypt.hashpw("admin".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            # Unlock account
            admin.failed_login_attempts = 0
            admin.locked_until = None
            admin.is_active = True
            admin.must_change_password = True

        db.commit()
        print("")
        print("╔══════════════════════════════════════╗")
        print("║     Admin Account Reset Complete     ║")
        print("╠══════════════════════════════════════╣")
        print("║  Username: admin                     ║")
        print("║  Password: admin                     ║")
        print("║                                      ║")
        print("║  Please change password after login  ║")
        print("╚══════════════════════════════════════╝")
        print("")

    except Exception as e:
        print(f"[X] Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    reset_admin()

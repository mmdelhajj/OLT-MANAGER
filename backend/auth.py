"""Authentication and Authorization module"""
import os
import secrets
import string
import logging
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from models import User, get_db

logger = logging.getLogger(__name__)

# Security settings
MAX_LOGIN_ATTEMPTS = 5  # Lock account after 5 failed attempts
LOCKOUT_DURATION_MINUTES = 15  # Lock for 15 minutes
MIN_PASSWORD_LENGTH = 8  # Minimum password length


def get_or_create_jwt_secret() -> str:
    """Get JWT secret from file, or create and persist a new one"""
    secret_file = "/etc/olt-manager/jwt.secret"

    # Try to read existing secret
    try:
        if os.path.exists(secret_file):
            with open(secret_file, 'r') as f:
                secret = f.read().strip()
                if secret:
                    return secret
    except Exception:
        pass

    # Check environment variable
    env_secret = os.environ.get("JWT_SECRET_KEY")
    if env_secret:
        return env_secret

    # Generate new secret and persist it
    new_secret = secrets.token_hex(32)
    try:
        os.makedirs("/etc/olt-manager", exist_ok=True)
        with open(secret_file, 'w') as f:
            f.write(new_secret)
        os.chmod(secret_file, 0o600)  # Only root can read
    except Exception:
        pass  # If we can't persist, use in-memory (will regenerate on restart)

    return new_secret


# Get or create persistent JWT secret key
SECRET_KEY = get_or_create_jwt_secret()
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

security = HTTPBearer(auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


def get_password_hash(password: str) -> str:
    """Hash a password"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    """Decode and verify a JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Get the current authenticated user from the token"""
    if not credentials:
        return None

    token = credentials.credentials
    payload = decode_token(token)
    if not payload:
        return None

    user_id = payload.get("user_id")
    if not user_id:
        return None

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    return user


def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Require authentication - raises 401 if not authenticated"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = get_current_user(credentials, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def require_admin(user: User = Depends(require_auth)) -> User:
    """Require admin role"""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return user


def generate_secure_password(length: int = 16) -> str:
    """Generate a cryptographically secure random password"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def validate_password_strength(password: str) -> tuple[bool, str]:
    """Validate password meets security requirements"""
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters"
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one number"
    return True, "Password is valid"


def check_account_lockout(user: User) -> tuple[bool, Optional[str]]:
    """Check if account is locked due to failed login attempts"""
    if user.locked_until and user.locked_until > datetime.utcnow():
        remaining = (user.locked_until - datetime.utcnow()).seconds // 60
        return True, f"Account locked. Try again in {remaining + 1} minutes"
    return False, None


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """Authenticate a user by username and password with rate limiting"""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return None

    # Check if account is locked
    is_locked, message = check_account_lockout(user)
    if is_locked:
        logger.warning(f"Login attempt on locked account: {username}")
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=message)

    if not verify_password(password, user.password_hash):
        # Increment failed attempts
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        if user.failed_login_attempts >= MAX_LOGIN_ATTEMPTS:
            user.locked_until = datetime.utcnow() + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
            logger.warning(f"Account locked due to {MAX_LOGIN_ATTEMPTS} failed attempts: {username}")
        db.commit()
        return None

    if not user.is_active:
        return None

    # Reset failed attempts on successful login
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = datetime.utcnow()
    db.commit()

    return user


def create_default_admin(db: Session):
    """Create default admin user if no users exist"""
    user_count = db.query(User).count()
    if user_count == 0:
        # Use simple default password for easier first-time access
        default_password = "admin"

        admin = User(
            username="admin",
            password_hash=get_password_hash(default_password),
            role="admin",
            full_name="Administrator",
            must_change_password=True  # Force password change on first login
        )
        db.add(admin)
        db.commit()

        print(f"[INFO] Created default admin user")
        print(f"[INFO] Username: admin")
        print(f"[INFO] Password: admin")
        print(f"[INFO] *** PLEASE CHANGE PASSWORD AFTER FIRST LOGIN ***")

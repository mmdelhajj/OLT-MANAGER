"""Authentication and Authorization module"""
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from models import User, get_db


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


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """Authenticate a user by username and password"""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    if not user.is_active:
        return None
    return user


def create_default_admin(db: Session):
    """Create default admin user if no users exist"""
    user_count = db.query(User).count()
    if user_count == 0:
        admin = User(
            username="admin",
            password_hash=get_password_hash("admin123"),
            role="admin",
            full_name="Administrator"
        )
        db.add(admin)
        db.commit()
        print("Created default admin user: admin / admin123")

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.config import settings
from app.core.logging_config import SafeLogger
from app.db.database import db

security = HTTPBearer(auto_error=False)

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Encodes JWT access token with user identification, role, and expiration."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": now})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decodes and validates JWT token."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        SafeLogger.warning("Token expired signature.")
        return None
    except jwt.InvalidTokenError as e:
        SafeLogger.warning(f"Invalid JWT token: {str(e)}")
        return None

def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Dict[str, Any]:
    """Dependency that extracts and validates authenticated user."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed authentication token payload.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User associated with token no longer exists.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user["is_demo"] = bool(user.get("is_demo", 0) or payload.get("is_demo", False))
    return user

def optional_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[Dict[str, Any]]:
    """Allows endpoints to optionally extract user context if present."""
    if not credentials:
        return None
    payload = decode_access_token(credentials.credentials)
    if not payload or not payload.get("sub"):
        return None
    user = db.get_user_by_id(payload["sub"])
    if user:
        user["is_demo"] = bool(user.get("is_demo", 0) or payload.get("is_demo", False))
    return user

def require_owner(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Strict server-side role check: requires OWNER role."""
    if current_user.get("role") != "OWNER":
        SafeLogger.warning(f"Unauthorized access attempt by user {current_user.get('email')} to owner endpoint.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: This action requires verified Store Owner privileges."
        )
    return current_user

def require_customer(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Strict server-side role check: requires CUSTOMER role."""
    if current_user.get("role") != "CUSTOMER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Customer account required."
        )
    return current_user

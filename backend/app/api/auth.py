from fastapi import APIRouter, HTTPException, Depends, status
from app.schemas.request import SignupRequest, LoginRequest, DemoSessionRequest
from app.schemas.response import AuthResponse, UserResponse
from app.core.auth import create_access_token, get_current_user
from app.db.database import db, verify_password
from app.core.logging_config import SafeLogger

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/demo-session", response_model=AuthResponse)
def create_demo_session(req: DemoSessionRequest) -> AuthResponse:
    """
    Creates an isolated demo session for either Customer or Store Owner portal.
    Does not require real credentials or expose backend passwords to frontend clients.
    """
    target_role = req.role.strip().upper()
    if target_role not in ("CUSTOMER", "OWNER"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid demo role '{req.role}'. Supported roles are 'CUSTOMER' and 'OWNER'."
        )

    user = db.get_demo_user(target_role)
    token = create_access_token(data={
        "sub": user["id"],
        "email": user["email"],
        "role": user["role"],
        "is_demo": True
    })

    SafeLogger.info(f"Initialized demo session for {target_role}: {user['email']}")
    return AuthResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(
            id=user["id"],
            email=user["email"],
            full_name=user["full_name"],
            role=user["role"],
            is_demo=True,
            created_at=user["created_at"]
        )
    )

@router.post("/signup", response_model=AuthResponse)
def signup(req: SignupRequest) -> AuthResponse:
    """Public signup for shoppers. CRITICAL: Strictly creates real CUSTOMER role only."""
    clean_email = req.email.strip().lower()
    if "@" not in clean_email or "." not in clean_email:
        raise HTTPException(status_code=400, detail="Please provide a valid email address.")

    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters long.")

    existing = db.get_user_by_email(clean_email)
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email address already exists. Please log in.")

    # Always enforce CUSTOMER role and non-demo status for public signup
    user = db.create_user(
        email=clean_email,
        full_name=req.full_name.strip(),
        password=req.password,
        role="CUSTOMER",
        is_demo=0
    )

    token = create_access_token(data={
        "sub": user["id"],
        "email": user["email"],
        "role": user["role"],
        "is_demo": False
    })

    SafeLogger.info(f"Customer registered: {clean_email}")
    return AuthResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(
            id=user["id"],
            email=user["email"],
            full_name=user["full_name"],
            role=user["role"],
            is_demo=False,
            created_at=user["created_at"]
        )
    )

@router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest) -> AuthResponse:
    """Authenticates customer or owner credentials."""
    clean_email = req.email.strip().lower()
    user = db.get_user_by_email(clean_email)
    pwd = req.password
    pwd_valid = False
    if user:
        pwd_valid = verify_password(pwd, user["hashed_password"]) or verify_password(pwd.strip(), user["hashed_password"])

    if not user or not pwd_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password. Please verify your credentials."
        )

    is_demo_user = bool(user.get("is_demo", 0))
    token = create_access_token(data={
        "sub": user["id"],
        "email": user["email"],
        "role": user["role"],
        "is_demo": is_demo_user
    })

    return AuthResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(
            id=user["id"],
            email=user["email"],
            full_name=user["full_name"],
            role=user["role"],
            is_demo=is_demo_user,
            created_at=user["created_at"]
        )
    )

@router.post("/owner-login", response_model=AuthResponse)
def owner_login(req: LoginRequest) -> AuthResponse:
    """Dedicated owner login endpoint with strict server-side role validation."""
    clean_email = req.email.strip().lower()
    user = db.get_user_by_email(clean_email)
    pwd = req.password
    pwd_valid = False
    if user:
        pwd_valid = verify_password(pwd, user["hashed_password"]) or verify_password(pwd.strip(), user["hashed_password"])

    if not user or not pwd_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid owner credentials."
        )

    if user["role"] != "OWNER":
        SafeLogger.warning(f"Unauthorized non-owner login attempt to /owner-login: {clean_email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: This login portal is restricted to authorized Store Owners."
        )

    is_demo_user = bool(user.get("is_demo", 0))
    token = create_access_token(data={
        "sub": user["id"],
        "email": user["email"],
        "role": "OWNER",
        "is_demo": is_demo_user
    })

    SafeLogger.info(f"Store owner authenticated: {clean_email}")
    return AuthResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(
            id=user["id"],
            email=user["email"],
            full_name=user["full_name"],
            role=user["role"],
            is_demo=is_demo_user,
            created_at=user["created_at"]
        )
    )

@router.get("/me", response_model=UserResponse)
def get_me(current_user: dict = Depends(get_current_user)) -> UserResponse:
    """Returns the authenticated profile of the current session."""
    return UserResponse(
        id=current_user["id"],
        email=current_user["email"],
        full_name=current_user["full_name"],
        role=current_user["role"],
        is_demo=bool(current_user.get("is_demo", False)),
        created_at=current_user["created_at"]
    )

@router.post("/logout")
def logout(current_user: dict = Depends(get_current_user)) -> dict:
    """Invalidates frontend session."""
    SafeLogger.info(f"User logged out: {current_user.get('email')}")
    return {"message": "Logged out successfully"}

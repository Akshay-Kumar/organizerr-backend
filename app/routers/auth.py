import os
from datetime import datetime, timedelta
from typing import Optional

import jwt
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from passlib.context import CryptContext
from sqlmodel import Session, select

from app.models import User
from app.schemas import TokenOut, UserCreateIn, UserOut
from app.utils.db import get_session

router = APIRouter(prefix="/auth", tags=["auth"])

SECRET_KEY = os.getenv("JWT_SECRET", "super-secret-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "4320")  # 3 days
)

# bcrypt config – THIS FIXES THE 72-BYTE ERROR
pwd_context = CryptContext(
    schemes=["bcrypt"],
    bcrypt__ident="2b",
    deprecated="auto"
)


def verify_password(plain: str, hashed: str) -> bool:
    """
    Always verify plain-text string password.
    """
    if not isinstance(plain, str):
        plain = plain.decode("utf-8")
    return pwd_context.verify(plain, hashed)


def get_password_hash(password: str) -> str:
    """
    Hash password safely as a UTF-8 string.
    """
    if not isinstance(password, str):
        password = password.decode("utf-8")

    # bcrypt silently truncates >72 bytes but this is SAFE.
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {
            "user_id": payload.get("user_id"),
            "username": payload.get("sub")
        }
    except jwt.PyJWTError:
        return None


# ---------------------------
# REGISTER USER
# ---------------------------
@router.post("/register", response_model=UserOut)
def register(user_in: UserCreateIn, session: Session = Depends(get_session)):

    # Username must be unique
    existing = session.exec(
        select(User).where(User.username == user_in.username)
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")

    # Hash plain-text password correctly
    hashed_password = get_password_hash(user_in.password)

    # Create user
    user = User(
        username=user_in.username,
        email=user_in.email,
        hashed_password=hashed_password
    )

    session.add(user)
    session.commit()
    session.refresh(user)

    return user


# ---------------------------
# LOGIN USER
# ---------------------------
@router.post("/login", response_model=TokenOut)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session)
):

    # Username lookup
    user = session.exec(
        select(User).where(User.username == form_data.username)
    ).first()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Password check
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Create JWT
    token = create_access_token({
        "sub": user.username,
        "user_id": user.id
    })

    return {
        "access_token": token,
        "token_type": "bearer"
    }

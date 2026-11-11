from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.middleware.auth import get_current_user
from app.models import User
from app.schemas.user import LoginIn, RegisterIn, TokenOut, UserOut
from app.utils.errors import AppError
from app.utils.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


def _token_response(user: User) -> TokenOut:
    return TokenOut(access_token=create_access_token(user.id), expires_in=settings.access_token_minutes * 60,
                    user=UserOut.model_validate(user))


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    """Create an ATTENDEE or ORGANISER account and sign in immediately."""
    if db.scalar(select(User.id).where(User.email == data.email)):
        raise AppError(409, "An account with this email already exists")
    user = User(name=data.name.strip(), email=data.email, password_hash=hash_password(data.password), role=data.role)
    db.add(user)
    db.commit()
    return _token_response(user)


@router.post("/login", response_model=TokenOut)
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == data.email.lower()))
    # Same message for "no such user" and "wrong password" so attackers can't discover which emails exist.
    if user is None or not verify_password(data.password, user.password_hash):
        raise AppError(401, "Incorrect email or password")
    if not user.is_active:
        raise AppError(403, "This account has been disabled")
    return _token_response(user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(_: User = Depends(get_current_user)):
    """JWTs are stateless: logging out = the client discards its token (tokens also expire on their own)."""
    return None

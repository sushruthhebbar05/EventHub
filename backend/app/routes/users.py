from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models import User
from app.schemas.user import UserOut, UserUpdate
from app.utils.errors import AppError
from app.utils.security import hash_password, verify_password

router = APIRouter(prefix="/api/users", tags=["Users"])


@router.get("/me", response_model=UserOut)
def get_profile(user: User = Depends(get_current_user)):
    return user


@router.patch("/me", response_model=UserOut)
def update_profile(data: UserUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if data.name:
        user.name = data.name.strip()
    if data.new_password:
        if not data.current_password or not verify_password(data.current_password, user.password_hash):
            raise AppError(400, "Current password is incorrect")
        user.password_hash = hash_password(data.new_password)
    db.commit()
    return user

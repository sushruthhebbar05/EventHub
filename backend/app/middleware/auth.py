"""Authentication + role-based authorisation dependencies.

The role is always read from the DATABASE (not trusted from the token), so a demoted or
disabled user loses access immediately.
"""
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.models.constants import Role
from app.utils.errors import AppError
from app.utils.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_optional_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    if creds is None:
        return None
    user_id = decode_access_token(creds.credentials)
    if user_id is None:
        raise AppError(401, "Invalid or expired token")
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise AppError(401, "Account not found or disabled")
    return user


def get_current_user(user: User | None = Depends(get_optional_user)) -> User:
    if user is None:
        raise AppError(401, "Not authenticated")
    return user


def require_roles(*roles: str):
    """Usage: `user = Depends(require_roles(Role.ORGANISER, Role.ADMIN))`"""

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise AppError(403, "You do not have permission to perform this action")
        return user

    return checker


require_organiser = require_roles(Role.ORGANISER, Role.ADMIN)
require_admin = require_roles(Role.ADMIN)

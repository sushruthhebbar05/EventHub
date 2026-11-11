from sqlalchemy import Boolean, CheckConstraint, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin
from app.models.constants import Role, in_list


class User(Base, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(in_list("role", [Role.ATTENDEE, Role.ORGANISER, Role.ADMIN]), name="ck_users_role"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default=Role.ATTENDEE, server_default=Role.ATTENDEE)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))

"""Application settings, read from environment variables (or a local .env file).

Nothing secret is hardcoded here: DATABASE_URL and JWT_SECRET must be provided.
"""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    jwt_secret: str = Field(min_length=16)
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60

    # Seat holds
    hold_seconds: int = 300              # 5 minutes
    expiry_sweep_seconds: int = 5        # how often the background job releases expired holds
    max_seats_per_booking: int = 6

    # Events
    require_event_approval: bool = True  # organiser events start as PENDING until an admin approves
    local_timezone: str = "Asia/Kolkata" # used for the "date" filter on the events list
    cancel_cutoff_hours: int = 24        # confirmed bookings can be cancelled until this long before the event

    cors_origins: str = "http://localhost:5173"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

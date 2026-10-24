import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DEV_JWT_SECRET = "dev-only-secret-change-me-0123456789abcdef"
DEV_PASSWORD = "demo-pass"


@dataclass(frozen=True)
class Settings:
    """All settings for the platform API, read once from environment variables."""

    database_url: str
    jwt_secret: str
    jwt_expire_minutes: int
    demo_password: str
    model_store: Path
    environment: str


# Reads environment variables into Settings. In production it refuses to start with dev secrets.
def load_settings() -> Settings:
    settings = Settings(
        database_url=os.environ.get("DATABASE_URL", "sqlite:///./platform.db"),
        jwt_secret=os.environ.get("JWT_SECRET", DEV_JWT_SECRET),
        jwt_expire_minutes=int(os.environ.get("JWT_EXPIRE_MINUTES", "30")),
        demo_password=os.environ.get("DEMO_PASSWORD", DEV_PASSWORD),
        model_store=Path(os.environ.get("MODEL_STORE", "./model-store")),
        environment=os.environ.get("APP_ENV", "dev"),
    )
    if settings.environment == "production":
        problems = []
        if settings.jwt_secret == DEV_JWT_SECRET or len(settings.jwt_secret) < 32:
            problems.append("JWT_SECRET must be set to at least 32 characters")
        if settings.demo_password == DEV_PASSWORD:
            problems.append("DEMO_PASSWORD must be set")
        if problems:
            raise RuntimeError("Refusing to start in production: " + "; ".join(problems))
    return settings


# Returns the same Settings object every time, so the environment is read once.
@lru_cache
def get_settings() -> Settings:
    return load_settings()

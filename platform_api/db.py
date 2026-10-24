from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from platform_api.config import get_settings


class Base(DeclarativeBase):
    """Parent class that all table models inherit from."""


# Builds the engine with short timeouts so a dead database fails fast instead of hanging threads.
def make_engine(url: str):
    if url.startswith("sqlite"):
        connect_args = {"check_same_thread": False, "timeout": 3}
    else:
        connect_args = {"connect_timeout": 3}
    return create_engine(url, connect_args=connect_args, pool_pre_ping=True, pool_timeout=3)


engine = make_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


# Dependency: hands one database session to each request and always closes it afterwards.
def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from platform_api.db import Base


# Current time in UTC, used for created and archived timestamps.
def utcnow() -> datetime:
    return datetime.now(UTC)


class Job(Base):
    """One training or batch job a team asked the platform to run."""

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    team: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(63))
    kind: Mapped[str] = mapped_column(String(16))
    image: Mapped[str] = mapped_column(String(200))
    cpu: Mapped[int] = mapped_column(Integer)
    memory_gb: Mapped[int] = mapped_column(Integer)
    gpu: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), index=True)
    manifest: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ModelVersion(Base):
    """One registered version of a team's model, and where it is in its life."""

    __tablename__ = "model_versions"
    __table_args__ = (UniqueConstraint("team", "name", "version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    team: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(63), index=True)
    version: Mapped[int] = mapped_column(Integer)
    accuracy: Mapped[float] = mapped_column(Float)
    stage: Mapped[str] = mapped_column(String(16))  # registered, production, archived, rolled_back
    artifact: Mapped[str] = mapped_column(String(100))  # file name inside the model's folder
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

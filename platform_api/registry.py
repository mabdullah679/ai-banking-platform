import json
import os
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from platform_api.config import get_settings
from platform_api.models import ModelVersion, utcnow
from platform_api.schemas import ModelVersionIn


# Dependency: the folder where model artifacts and pointers live. Tests replace this.
def get_model_store() -> Path:
    return get_settings().model_store


# Where one model's files live: <store>/<team>/<model name>/.
def model_dir(store: Path, team: str, name: str) -> Path:
    return store / team / name


# Writes a file in one step so a reader never sees half of it (write a temp file, then rename).
def atomic_write(path: Path, content: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(content))
    os.replace(tmp, path)


# Saves a new model version as an artifact file and a database row, at the next version number.
def register_version(
    db: Session, store: Path, team: str, name: str, body: ModelVersionIn
) -> ModelVersion:
    last = db.scalar(
        select(func.max(ModelVersion.version)).where(
            ModelVersion.team == team, ModelVersion.name == name
        )
    )
    version = (last or 0) + 1
    artifact = f"v{version}.json"
    atomic_write(
        model_dir(store, team, name) / artifact, {"weights": body.weights, "bias": body.bias}
    )
    row = ModelVersion(
        team=team,
        name=name,
        version=version,
        accuracy=body.accuracy,
        stage="registered",
        artifact=artifact,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# Points the model server at one version by rewriting the small current.json pointer file.
def write_pointer(store: Path, row: ModelVersion) -> None:
    pointer = {"name": row.name, "version": row.version, "artifact": row.artifact}
    atomic_write(model_dir(store, row.team, row.name) / "current.json", pointer)


# Finds a model version for a team, or raises 404 (also 404 for another team's model).
def get_version(db: Session, team: str, name: str, version: int) -> ModelVersion:
    row = db.scalar(
        select(ModelVersion).where(
            ModelVersion.team == team, ModelVersion.name == name, ModelVersion.version == version
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Model version not found")
    return row


# Makes one version the live one. The old live version is archived so it can be rolled back to.
def promote(db: Session, store: Path, team: str, name: str, version: int) -> ModelVersion:
    row = get_version(db, team, name, version)
    if row.stage == "production":
        raise HTTPException(status_code=409, detail="Already in production")
    live = db.scalar(
        select(ModelVersion).where(
            ModelVersion.team == team, ModelVersion.name == name, ModelVersion.stage == "production"
        )
    )
    if live is not None:
        live.stage = "archived"
        live.archived_at = utcnow()
    row.stage = "production"
    row.archived_at = None
    db.commit()
    write_pointer(store, row)
    return row


# Puts the most recently archived version back in production and marks the current one rolled back.
def rollback(db: Session, store: Path, team: str, name: str) -> ModelVersion:
    live = db.scalar(
        select(ModelVersion).where(
            ModelVersion.team == team, ModelVersion.name == name, ModelVersion.stage == "production"
        )
    )
    previous = db.scalar(
        select(ModelVersion)
        .where(
            ModelVersion.team == team,
            ModelVersion.name == name,
            ModelVersion.stage == "archived",
        )
        .order_by(ModelVersion.archived_at.desc())
    )
    if live is None or previous is None:
        raise HTTPException(status_code=409, detail="Nothing to roll back to")
    live.stage = "rolled_back"
    previous.stage = "production"
    previous.archived_at = None
    db.commit()
    write_pointer(store, previous)
    return previous

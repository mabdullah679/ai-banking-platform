from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from platform_api import registry
from platform_api.auth import Principal, get_principal
from platform_api.db import get_db
from platform_api.models import ModelVersion
from platform_api.schemas import ModelVersionIn, ModelVersionOut

router = APIRouter(prefix="/models", tags=["models"])
NAME = r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$"


# Registers a new version of a team's model. It starts as "registered", not live.
@router.post("/{name}/versions", response_model=ModelVersionOut, status_code=201)
def register(
    name: str,
    body: ModelVersionIn,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
    store: Path = Depends(registry.get_model_store),
) -> ModelVersion:
    return registry.register_version(db, store, principal.team, name, body)


# Lists all versions of one of the caller's team's models.
@router.get("/{name}/versions", response_model=list[ModelVersionOut])
def versions(
    name: str, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)
) -> list[ModelVersion]:
    query = (
        select(ModelVersion)
        .where(ModelVersion.team == principal.team, ModelVersion.name == name)
        .order_by(ModelVersion.version)
    )
    return list(db.scalars(query))


# Makes a version the live one. The model server picks it up without a restart.
@router.post("/{name}/versions/{version}/promote", response_model=ModelVersionOut)
def promote(
    name: str,
    version: int,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
    store: Path = Depends(registry.get_model_store),
) -> ModelVersion:
    return registry.promote(db, store, principal.team, name, version)


# Puts the previously live version back, fast, without a deploy.
@router.post("/{name}/rollback", response_model=ModelVersionOut)
def rollback(
    name: str,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
    store: Path = Depends(registry.get_model_store),
) -> ModelVersion:
    return registry.rollback(db, store, principal.team, name)

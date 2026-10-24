from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from platform_api.auth import Principal, get_principal
from platform_api.db import get_db
from platform_api.models import Job
from platform_api.quota import TEAM_QUOTAS, usage_of
from platform_api.schemas import TeamOut

router = APIRouter(prefix="/teams", tags=["teams"])


# Shows the caller's team quota next to what the team is using right now.
@router.get("/me", response_model=TeamOut)
def my_team(
    principal: Principal = Depends(get_principal), db: Session = Depends(get_db)
) -> TeamOut:
    quota = TEAM_QUOTAS.get(principal.team)
    if quota is None:
        raise HTTPException(status_code=404, detail="Your team has no quota")
    jobs = db.scalars(select(Job).where(Job.team == principal.team))
    return TeamOut.model_validate(
        {"team": principal.team, "quota": asdict(quota), "usage": asdict(usage_of(jobs))}
    )

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from platform_api.auth import Principal, get_principal, require_admin
from platform_api.db import get_db
from platform_api.models import Job
from platform_api.quota import (
    ACTIVE_STATUSES,
    TEAM_QUOTAS,
    QuotaExceeded,
    check_admission,
    usage_of,
)
from platform_api.runner import JobRunner, get_runner
from platform_api.schemas import JobIn, JobOut, JobStatusIn

router = APIRouter(prefix="/jobs", tags=["jobs"])

# Which status changes the job controller may report.
ALLOWED_TRANSITIONS = {"queued": {"running"}, "running": {"succeeded", "failed"}}


# Finds a job in the caller's own team. Another team's job is a 404, so its existence is not leaked.
def own_job(db: Session, principal: Principal, job_id: int) -> Job:
    job = db.get(Job, job_id)
    if job is None or job.team != principal.team:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


# Submits a job. Admission control checks the team's quota first; over quota is a 409.
@router.post("", response_model=JobOut, status_code=201)
def submit_job(
    body: JobIn,
    request: Request,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
    runner: JobRunner = Depends(get_runner),
) -> Job:
    quota = TEAM_QUOTAS.get(principal.team)
    if quota is None:
        raise HTTPException(status_code=403, detail="Your team has no quota")
    counter = request.app.state.job_counter
    active = db.scalars(
        select(Job).where(Job.team == principal.team, Job.status.in_(ACTIVE_STATUSES))
    )
    try:
        check_admission(quota, usage_of(active), body.cpu, body.memory_gb, body.gpu)
    except QuotaExceeded as exc:
        counter.labels(principal.team, "rejected_quota").inc()
        raise HTTPException(status_code=409, detail=f"Quota exceeded: {exc}") from None
    job = Job(team=principal.team, status="queued", manifest={}, **body.model_dump())
    db.add(job)
    db.flush()  # assigns the job its ID, which the manifest needs
    job.manifest = runner.submit(job)
    db.commit()
    db.refresh(job)
    counter.labels(principal.team, "accepted").inc()
    return job


# Lists the caller's own team's jobs, newest first.
@router.get("", response_model=list[JobOut])
def list_jobs(
    principal: Principal = Depends(get_principal), db: Session = Depends(get_db)
) -> list[Job]:
    query = select(Job).where(Job.team == principal.team).order_by(Job.id.desc())
    return list(db.scalars(query))


# Shows one job of the caller's team.
@router.get("/{job_id}", response_model=JobOut)
def get_job(
    job_id: int, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)
) -> Job:
    return own_job(db, principal, job_id)


# Cancels a queued or running job, which frees its quota.
@router.delete("/{job_id}", response_model=JobOut)
def cancel_job(
    job_id: int, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)
) -> Job:
    job = own_job(db, principal, job_id)
    if job.status not in ACTIVE_STATUSES:
        raise HTTPException(status_code=409, detail=f"Job is already {job.status}")
    job.status = "cancelled"
    db.commit()
    return job


# The job controller reports progress here (platform admin only). Frees quota when a job ends.
@router.patch("/{job_id}/status", response_model=JobOut)
def report_status(
    job_id: int,
    body: JobStatusIn,
    _admin: Principal = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if body.status not in ALLOWED_TRANSITIONS.get(job.status, set()):
        raise HTTPException(status_code=409, detail=f"Cannot go from {job.status} to {body.status}")
    job.status = body.status
    db.commit()
    return job

from collections.abc import Iterable
from dataclasses import dataclass

from platform_api.models import Job

ACTIVE_STATUSES = ("queued", "running")


@dataclass(frozen=True)
class Quota:
    """The most a team may use at the same time."""

    max_active_jobs: int
    max_cpu: int
    max_memory_gb: int
    max_gpu: int


@dataclass(frozen=True)
class Usage:
    """What a team is using right now."""

    active_jobs: int
    cpu: int
    memory_gb: int
    gpu: int


# In real life this comes from a database or the Kubernetes ResourceQuota. Kept in code for clarity.
# Keep these numbers in step with infra/k8s/teams.yaml.
TEAM_QUOTAS: dict[str, Quota] = {
    "team-a": Quota(max_active_jobs=2, max_cpu=8, max_memory_gb=32, max_gpu=1),
    "team-b": Quota(max_active_jobs=1, max_cpu=4, max_memory_gb=16, max_gpu=0),
}


class QuotaExceeded(Exception):
    """Raised when a new job would push a team over one of its limits."""


# Adds up the resources of a team's queued and running jobs.
def usage_of(jobs: Iterable[Job]) -> Usage:
    active = [job for job in jobs if job.status in ACTIVE_STATUSES]
    return Usage(
        active_jobs=len(active),
        cpu=sum(job.cpu for job in active),
        memory_gb=sum(job.memory_gb for job in active),
        gpu=sum(job.gpu for job in active),
    )


# Admission control: refuses a new job that would exceed any limit, and says which one.
def check_admission(quota: Quota, usage: Usage, cpu: int, memory_gb: int, gpu: int) -> None:
    if usage.active_jobs + 1 > quota.max_active_jobs:
        raise QuotaExceeded(f"active jobs limit is {quota.max_active_jobs}")
    if usage.cpu + cpu > quota.max_cpu:
        raise QuotaExceeded(f"cpu limit is {quota.max_cpu} (in use {usage.cpu}, asked {cpu})")
    if usage.memory_gb + memory_gb > quota.max_memory_gb:
        raise QuotaExceeded(
            f"memory limit is {quota.max_memory_gb} GB "
            f"(in use {usage.memory_gb}, asked {memory_gb})"
        )
    if usage.gpu + gpu > quota.max_gpu:
        raise QuotaExceeded(f"gpu limit is {quota.max_gpu} (in use {usage.gpu}, asked {gpu})")

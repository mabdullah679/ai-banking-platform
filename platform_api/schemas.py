from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

K8S_NAME = r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$"


class TokenRequest(BaseModel):
    """What a caller sends to log in."""

    username: str
    password: str


class TokenResponse(BaseModel):
    """What the caller gets back after a successful login."""

    access_token: str
    token_type: str = "bearer"


class JobIn(BaseModel):
    """A job a team wants to run. Limits stop absurd requests before they reach admission."""

    name: str = Field(pattern=K8S_NAME, max_length=40)
    kind: Literal["training", "batch"]
    image: str = Field(min_length=1, max_length=200)
    cpu: int = Field(ge=1, le=64)
    memory_gb: int = Field(ge=1, le=512)
    gpu: int = Field(default=0, ge=0, le=8)


class JobOut(BaseModel):
    """A job as shown to its team, including the Kubernetes Job manifest the platform rendered."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    team: str
    name: str
    kind: str
    image: str
    cpu: int
    memory_gb: int
    gpu: int
    status: str
    manifest: dict


class JobStatusIn(BaseModel):
    """A status report from the job controller (platform admin only)."""

    status: Literal["running", "succeeded", "failed"]


class QuotaOut(BaseModel):
    """A team's limits."""

    max_active_jobs: int
    max_cpu: int
    max_memory_gb: int
    max_gpu: int


class UsageOut(BaseModel):
    """What a team is using right now (queued and running jobs)."""

    active_jobs: int
    cpu: int
    memory_gb: int
    gpu: int


class TeamOut(BaseModel):
    """A team's quota next to its current usage."""

    team: str
    quota: QuotaOut
    usage: UsageOut


class ModelVersionIn(BaseModel):
    """A model to register. The model here is a simple linear scorer: weights and a bias."""

    weights: list[float] = Field(min_length=1, max_length=1000)
    bias: float
    accuracy: float = Field(ge=0, le=1)


class ModelVersionOut(BaseModel):
    """A registered model version."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    version: int
    stage: str
    accuracy: float
    artifact: str

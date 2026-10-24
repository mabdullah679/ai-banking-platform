import time

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from platform_api.auth import ALGORITHM, AUDIENCE
from platform_api.config import get_settings, load_settings
from platform_api.db import get_db
from platform_api.main import app
from platform_api.models import Job
from platform_api.quota import Quota, QuotaExceeded, Usage, check_admission
from platform_api.runner import render_k8s_job

JOB = {"name": "train-churn", "kind": "training", "image": "ml/train:1", "cpu": 2, "memory_gb": 8}


# Health needs no login, and readiness passes when the database answers.
def test_health_and_ready(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").status_code == 200


# Wrong password is 401, no token is 401, a forged token is 401, an expired token is 401.
def test_authentication_failures(client: TestClient) -> None:
    bad = client.post("/token", json={"username": "alice", "password": "nope"})
    assert bad.status_code == 401
    assert client.get("/jobs").status_code == 401
    claims = {"sub": "x", "team": "team-a", "role": "admin", "aud": AUDIENCE}
    forged = jwt.encode({**claims, "exp": time.time() + 600}, "wrong-key-" * 4, algorithm=ALGORITHM)
    expired = jwt.encode(
        {**claims, "exp": time.time() - 10}, get_settings().jwt_secret, algorithm=ALGORITHM
    )
    for token in (forged, expired):
        response = client.get("/jobs", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401


# A job within quota is accepted, and the platform renders a Kubernetes Job in the team namespace.
def test_submit_job_renders_manifest(client: TestClient, team_a: dict[str, str]) -> None:
    response = client.post("/jobs", json=JOB, headers=team_a)
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "queued"
    manifest = body["manifest"]
    assert manifest["kind"] == "Job"
    assert manifest["metadata"]["namespace"] == "team-a"
    pod = manifest["spec"]["template"]["spec"]
    assert pod["securityContext"]["runAsNonRoot"] is True
    assert pod["containers"][0]["resources"]["limits"]["memory"] == "8Gi"


# Asking for a GPU adds the GPU limit to the manifest; no GPU means no GPU entry.
def test_gpu_in_manifest() -> None:
    gpu_job = Job(
        id=7, team="team-a", name="gpu", kind="training", image="i", cpu=1, memory_gb=1, gpu=1
    )
    plain_job = Job(
        id=8, team="team-a", name="cpu", kind="batch", image="i", cpu=1, memory_gb=1, gpu=0
    )
    gpu_limits = render_k8s_job(gpu_job)["spec"]["template"]["spec"]["containers"][0]["resources"]
    cpu_limits = render_k8s_job(plain_job)["spec"]["template"]["spec"]["containers"][0]["resources"]
    assert gpu_limits["limits"]["nvidia.com/gpu"] == "1"
    assert "nvidia.com/gpu" not in cpu_limits["limits"]


# Team B has no GPU quota, so a GPU job is refused with 409 and a reason.
def test_gpu_quota_zero_is_409(client: TestClient, team_b: dict[str, str]) -> None:
    response = client.post("/jobs", json={**JOB, "gpu": 1}, headers=team_b)
    assert response.status_code == 409
    assert "gpu limit" in response.json()["detail"]


# Team B may run one job at a time: the second is refused, and finishing the first frees the slot.
def test_active_job_limit_and_release(
    client: TestClient, team_b: dict[str, str], admin: dict[str, str]
) -> None:
    first = client.post("/jobs", json=JOB, headers=team_b).json()
    second = client.post("/jobs", json={**JOB, "name": "other"}, headers=team_b)
    assert second.status_code == 409
    assert (
        client.patch(
            f"/jobs/{first['id']}/status", json={"status": "running"}, headers=admin
        ).status_code
        == 200
    )
    done = client.patch(f"/jobs/{first['id']}/status", json={"status": "succeeded"}, headers=admin)
    assert done.json()["status"] == "succeeded"
    assert client.post("/jobs", json={**JOB, "name": "other"}, headers=team_b).status_code == 201


# Cancelling a job frees its quota, and cancelling twice is a 409.
def test_cancel_frees_quota(client: TestClient, team_b: dict[str, str]) -> None:
    job = client.post("/jobs", json=JOB, headers=team_b).json()
    assert client.delete(f"/jobs/{job['id']}", headers=team_b).json()["status"] == "cancelled"
    assert client.delete(f"/jobs/{job['id']}", headers=team_b).status_code == 409
    assert client.get("/teams/me", headers=team_b).json()["usage"]["active_jobs"] == 0


# One team cannot see or cancel another team's job. It looks like the job does not exist (404).
def test_team_isolation(client: TestClient, team_a: dict[str, str], team_b: dict[str, str]) -> None:
    job = client.post("/jobs", json=JOB, headers=team_a).json()
    assert client.get(f"/jobs/{job['id']}", headers=team_b).status_code == 404
    assert client.delete(f"/jobs/{job['id']}", headers=team_b).status_code == 404
    assert client.get("/jobs", headers=team_b).json() == []
    assert len(client.get("/jobs", headers=team_a).json()) == 1


# Only platform admins can report job status, and illegal status jumps are refused.
def test_status_report_rules(
    client: TestClient, team_a: dict[str, str], admin: dict[str, str]
) -> None:
    job = client.post("/jobs", json=JOB, headers=team_a).json()
    url = f"/jobs/{job['id']}/status"
    assert client.patch(url, json={"status": "running"}, headers=team_a).status_code == 403
    assert client.patch(url, json={"status": "succeeded"}, headers=admin).status_code == 409
    assert client.patch(url, json={"status": "running"}, headers=admin).status_code == 200


# Bad job requests are rejected with 422 before reaching admission control.
def test_bad_job_is_422(client: TestClient, team_a: dict[str, str]) -> None:
    for bad in ({**JOB, "name": "Bad_Name"}, {**JOB, "cpu": 0}, {**JOB, "kind": "mining"}):
        assert client.post("/jobs", json=bad, headers=team_a).status_code == 422


# The quota rule on its own: usage plus the request must stay within every limit.
def test_check_admission_unit() -> None:
    quota = Quota(max_active_jobs=2, max_cpu=4, max_memory_gb=8, max_gpu=0)
    check_admission(quota, Usage(1, 2, 4, 0), cpu=2, memory_gb=4, gpu=0)
    with pytest.raises(QuotaExceeded, match="cpu"):
        check_admission(quota, Usage(1, 3, 4, 0), cpu=2, memory_gb=4, gpu=0)


# Quota usage is reported to the team.
def test_team_usage(client: TestClient, team_a: dict[str, str]) -> None:
    client.post("/jobs", json=JOB, headers=team_a)
    body = client.get("/teams/me", headers=team_a).json()
    assert body["usage"] == {"active_jobs": 1, "cpu": 2, "memory_gb": 8, "gpu": 0}
    assert body["quota"]["max_gpu"] == 1


# A dead database gives a clean 503 with Retry-After, not a bare 500.
def test_database_down_is_503(client: TestClient, team_a: dict[str, str]) -> None:
    class DeadSession:
        def scalars(self, *args: object, **kwargs: object) -> None:
            raise OperationalError("SELECT", {}, Exception("connection refused"))

    def dead_db():
        yield DeadSession()

    app.dependency_overrides[get_db] = dead_db
    response = client.get("/jobs", headers=team_a)
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "5"


# Every response carries a request ID, and a caller-supplied one is echoed back.
def test_request_id(client: TestClient) -> None:
    assert client.get("/health").headers["X-Request-ID"]
    assert client.get("/health", headers={"X-Request-ID": "abc"}).headers["X-Request-ID"] == "abc"


# /metrics exposes request metrics and the job counter, labelled by route pattern.
def test_metrics(client: TestClient, team_b: dict[str, str]) -> None:
    client.post("/jobs", json={**JOB, "gpu": 1}, headers=team_b)
    body = client.get("/metrics").text
    assert 'path="/jobs"' in body
    assert 'platform_jobs_submitted_total{result="rejected_quota",team="team-b"}' in body
    assert "http_request_duration_seconds_bucket" in body


# In production the app refuses to start with development secrets.
def test_production_refuses_dev_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        load_settings()
    monkeypatch.setenv("JWT_SECRET", "x" * 40)
    with pytest.raises(RuntimeError, match="DEMO_PASSWORD"):
        load_settings()
    monkeypatch.setenv("DEMO_PASSWORD", "a-real-password")
    assert load_settings().environment == "production"

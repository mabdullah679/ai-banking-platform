"""Staging gate: runs against the real docker compose stack (see scripts/staging.sh).

Not part of the default `pytest` run (testpaths is `tests`). Needs the stack on localhost:
platform-api 8000, model-server 8001, Prometheus 9090, Grafana 3000. Backend/API checks only:
nothing here drives a browser.
"""

import time

import httpx
import pytest

API, MODEL, PROM, GRAFANA = (
    "http://localhost:8000",
    "http://localhost:8001",
    "http://localhost:9090",
    "http://localhost:3000",
)
JOB = {"name": "train-a", "kind": "training", "image": "ml/train:1", "cpu": 2, "memory_gb": 8}


def login(user: str) -> dict[str, str]:
    r = httpx.post(f"{API}/token", json={"username": user, "password": "demo-pass"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def wait_for(check, seconds: int = 60):
    deadline = time.time() + seconds
    last = None
    while time.time() < deadline:
        try:
            last = check()
            if last:
                return last
        except httpx.HTTPError:
            pass
        time.sleep(1)
    pytest.fail(f"timed out after {seconds}s; last value: {last!r}")


def test_services_up() -> None:
    wait_for(lambda: httpx.get(f"{API}/ready").status_code == 200)
    assert httpx.get(f"{API}/health").json() == {"status": "ok"}
    assert httpx.get(f"{MODEL}/health").json() == {"status": "ok"}


def test_model_server_not_ready_before_first_promotion() -> None:
    assert httpx.get(f"{MODEL}/ready").status_code == 503


def test_quota_and_isolation() -> None:
    alice, bob = login("alice"), login("bob")
    first = httpx.post(f"{API}/jobs", json=JOB, headers=alice)
    assert first.status_code == 201
    assert first.json()["manifest"]["kind"] == "Job"
    second = httpx.post(f"{API}/jobs", json={**JOB, "name": "train-b"}, headers=alice)
    assert second.status_code == 201
    over = httpx.post(f"{API}/jobs", json={**JOB, "name": "train-c"}, headers=alice)
    assert over.status_code == 409 and "active jobs limit" in over.json()["detail"]
    gpu = httpx.post(f"{API}/jobs", json={**JOB, "gpu": 1}, headers=bob)
    assert gpu.status_code == 409 and "gpu limit" in gpu.json()["detail"]
    assert httpx.get(f"{API}/jobs/{first.json()['id']}", headers=bob).status_code == 404


def test_admin_only_status_report() -> None:
    alice, root = login("alice"), login("root")
    job_id = httpx.get(f"{API}/jobs", headers=alice).json()[0]["id"]
    body = {"status": "running"}
    assert httpx.patch(f"{API}/jobs/{job_id}/status", json=body, headers=alice).status_code == 403
    assert httpx.patch(f"{API}/jobs/{job_id}/status", json=body, headers=root).status_code == 200


def test_promote_serve_rollback_across_containers() -> None:
    alice = login("alice")
    base = f"{API}/models/churn/versions"
    for weights in ([1.0, 2.0], [10.0, 20.0]):
        r = httpx.post(base, json={"weights": weights, "bias": 0.5, "accuracy": 0.9}, headers=alice)
        assert r.status_code == 201
    predict = lambda: httpx.post(f"{MODEL}/predict", json={"features": [1, 1]}).json()  # noqa: E731

    assert httpx.post(f"{base}/1/promote", headers=alice).status_code == 200
    wait_for(lambda: httpx.get(f"{MODEL}/ready").status_code == 200)
    assert predict()["version"] == 1 and predict()["prediction"] == 3.5

    assert httpx.post(f"{base}/2/promote", headers=alice).status_code == 200
    wait_for(lambda: predict().get("version") == 2)
    assert predict()["prediction"] == 30.5

    assert httpx.post(f"{API}/models/churn/rollback", headers=alice).status_code == 200
    wait_for(lambda: predict().get("version") == 1)
    assert httpx.get(f"{base}", headers=login("bob")).json() == []


def test_prometheus_scrapes_both_services_and_loads_rules() -> None:
    def targets_up() -> bool:
        t = httpx.get(f"{PROM}/api/v1/targets").json()["data"]["activeTargets"]
        return len(t) == 2 and all(x["health"] == "up" for x in t)

    wait_for(targets_up, 60)
    groups = httpx.get(f"{PROM}/api/v1/rules").json()["data"]["groups"]
    assert sum(len(g["rules"]) for g in groups) == 12


def test_grafana_dashboard_provisioned() -> None:
    wait_for(lambda: httpx.get(f"{GRAFANA}/api/health").json().get("database") == "ok")
    found = wait_for(lambda: httpx.get(f"{GRAFANA}/api/search", params={"type": "dash-db"}).json())
    assert found, "no dashboard provisioned"
    ds = httpx.get(f"{GRAFANA}/api/datasources").json()
    assert any(d["type"] == "prometheus" for d in ds)

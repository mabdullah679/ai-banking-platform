import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

from model_server.main import create_app

V1 = {"weights": [1.0, 2.0], "bias": 0.5, "accuracy": 0.8}
V2 = {"weights": [10.0, 20.0], "bias": 1.0, "accuracy": 0.9}


# Reads the pointer file the platform writes for the model server.
def pointer(store: Path, team: str = "team-a", name: str = "churn") -> dict:
    return json.loads((store / team / name / "current.json").read_text())


# Registering makes numbered versions that start as "registered", not live.
def test_register_versions(client: TestClient, team_a: dict[str, str], store: Path) -> None:
    first = client.post("/models/churn/versions", json=V1, headers=team_a).json()
    second = client.post("/models/churn/versions", json=V2, headers=team_a).json()
    assert (first["version"], second["version"]) == (1, 2)
    assert first["stage"] == "registered"
    assert not (store / "team-a" / "churn" / "current.json").exists()


# Promote writes the pointer, archives the old live version, and rollback puts it back.
def test_promote_and_rollback(client: TestClient, team_a: dict[str, str], store: Path) -> None:
    client.post("/models/churn/versions", json=V1, headers=team_a)
    client.post("/models/churn/versions", json=V2, headers=team_a)
    assert client.post("/models/churn/versions/1/promote", headers=team_a).status_code == 200
    assert pointer(store)["version"] == 1
    assert client.post("/models/churn/versions/2/promote", headers=team_a).status_code == 200
    assert pointer(store)["version"] == 2
    stages = {
        v["version"]: v["stage"]
        for v in client.get("/models/churn/versions", headers=team_a).json()
    }
    assert stages == {1: "archived", 2: "production"}
    back = client.post("/models/churn/rollback", headers=team_a)
    assert back.json()["version"] == 1
    assert pointer(store)["version"] == 1
    stages = {
        v["version"]: v["stage"]
        for v in client.get("/models/churn/versions", headers=team_a).json()
    }
    assert stages == {1: "production", 2: "rolled_back"}


# Rollback with nothing to go back to, and promoting twice, are 409 not silent no-ops.
def test_rollback_and_promote_conflicts(client: TestClient, team_a: dict[str, str]) -> None:
    assert client.post("/models/churn/rollback", headers=team_a).status_code == 409
    client.post("/models/churn/versions", json=V1, headers=team_a)
    client.post("/models/churn/versions/1/promote", headers=team_a)
    assert client.post("/models/churn/versions/1/promote", headers=team_a).status_code == 409
    assert client.post("/models/churn/rollback", headers=team_a).status_code == 409


# Teams cannot touch each other's models: another team's version is a 404.
def test_model_team_isolation(
    client: TestClient, team_a: dict[str, str], team_b: dict[str, str]
) -> None:
    client.post("/models/churn/versions", json=V1, headers=team_a)
    assert client.post("/models/churn/versions/1/promote", headers=team_b).status_code == 404
    assert client.get("/models/churn/versions", headers=team_b).json() == []


# The model server is alive but NOT ready until a model has been promoted.
def test_server_not_ready_without_model(tmp_path: Path) -> None:
    server = TestClient(create_app(tmp_path / "missing" / "current.json"))
    assert server.get("/health").status_code == 200
    assert server.get("/ready").status_code == 503
    assert server.post("/predict", json={"features": [1, 2]}).status_code == 503


# End to end: the platform promotes, the server serves; promote again and rollback change it live.
def test_server_follows_promote_and_rollback(
    client: TestClient, team_a: dict[str, str], store: Path
) -> None:
    client.post("/models/churn/versions", json=V1, headers=team_a)
    client.post("/models/churn/versions", json=V2, headers=team_a)
    server = TestClient(create_app(store / "team-a" / "churn" / "current.json"))
    client.post("/models/churn/versions/1/promote", headers=team_a)
    first = server.post("/predict", json={"features": [1, 1]}).json()
    assert (first["version"], first["prediction"]) == (1, 3.5)
    client.post("/models/churn/versions/2/promote", headers=team_a)
    second = server.post("/predict", json={"features": [1, 1]}).json()
    assert (second["version"], second["prediction"]) == (2, 31.0)
    client.post("/models/churn/rollback", headers=team_a)
    assert server.post("/predict", json={"features": [1, 1]}).json()["version"] == 1


# Wrong feature count is a 422 that says what was expected.
def test_predict_wrong_feature_count(
    client: TestClient, team_a: dict[str, str], store: Path
) -> None:
    client.post("/models/churn/versions", json=V1, headers=team_a)
    client.post("/models/churn/versions/1/promote", headers=team_a)
    server = TestClient(create_app(store / "team-a" / "churn" / "current.json"))
    response = server.post("/predict", json={"features": [1, 2, 3]})
    assert response.status_code == 422
    assert "Expected 2" in response.json()["detail"]


# A broken new version is refused, the old model keeps serving, and the failure is counted.
def test_bad_version_keeps_old_model(tmp_path: Path) -> None:
    folder = tmp_path / "m"
    folder.mkdir()
    (folder / "v1.json").write_text(json.dumps({"weights": [1.0], "bias": 0}))
    ptr = folder / "current.json"
    ptr.write_text(json.dumps({"name": "m", "version": 1, "artifact": "v1.json"}))
    server = TestClient(create_app(ptr))
    assert server.post("/predict", json={"features": [2]}).json()["prediction"] == 2
    ptr.write_text(json.dumps({"name": "m", "version": 2, "artifact": "missing.json"}))
    os.utime(ptr, ns=(1, 1))  # make the change visible even if the clock tick is too coarse
    response = server.post("/predict", json={"features": [2]})
    assert response.status_code == 200 and response.json()["version"] == 1
    assert "model_reload_errors 1.0" in server.get("/metrics").text


# The server exposes which version is live and counts predictions per version.
def test_server_metrics(client: TestClient, team_a: dict[str, str], store: Path) -> None:
    client.post("/models/churn/versions", json=V1, headers=team_a)
    client.post("/models/churn/versions/1/promote", headers=team_a)
    server = TestClient(create_app(store / "team-a" / "churn" / "current.json"))
    server.post("/predict", json={"features": [1, 1]})
    text = server.get("/metrics").text
    assert 'model_loaded_info{model="churn",version="1"} 1.0' in text
    assert 'model_predictions_total{model="churn",version="1"} 1.0' in text

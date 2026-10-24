from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from platform_api.db import Base, get_db
from platform_api.main import app
from platform_api.registry import get_model_store


# Gives each test a fresh in-memory database and a temporary model folder, wired into the app.
@pytest.fixture()
def store(tmp_path: Path) -> Path:
    return tmp_path / "model-store"


@pytest.fixture()
def client(store: Path) -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    # Replaces the real database session with the test one for every request.
    def override_get_db() -> Iterator[Session]:
        with TestSession() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_model_store] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


# Logs in as a demo user and returns the Authorization header for later calls.
def login(client: TestClient, username: str) -> dict[str, str]:
    response = client.post("/token", json={"username": username, "password": "demo-pass"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture()
def team_a(client: TestClient) -> dict[str, str]:
    return login(client, "alice")


@pytest.fixture()
def team_b(client: TestClient) -> dict[str, str]:
    return login(client, "bob")


@pytest.fixture()
def admin(client: TestClient) -> dict[str, str]:
    return login(client, "root")

import os
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from prometheus_client import Counter, Gauge
from pydantic import BaseModel, Field

from common.observability import add_observability
from model_server.model import ModelStore

SERVICE = "model-server"


class PredictIn(BaseModel):
    """The numbers to score."""

    features: list[float] = Field(min_length=1, max_length=1000)


class PredictOut(BaseModel):
    """The score, plus which model and version produced it."""

    prediction: float
    model: str
    version: int


# Builds the model server. The pointer file says which model version is live.
def create_app(pointer: Path | None = None) -> FastAPI:
    pointer = pointer or Path(
        os.environ.get("MODEL_POINTER", "./model-store/team-a/churn/current.json")
    )
    app = FastAPI(title="model-server")
    registry = add_observability(app, SERVICE)
    store = ModelStore(pointer)
    app.state.store = store
    predictions = Counter(
        "model_predictions_total", "Predictions served", ["model", "version"], registry=registry
    )
    loaded = Gauge(
        "model_loaded_info",
        "The live model version (value is 1)",
        ["model", "version"],
        registry=registry,
    )
    reload_errors = Gauge(
        "model_reload_errors", "Bad model versions refused since start", registry=registry
    )

    # Refreshes the model from the pointer file and updates the gauges.
    def current(request: Request) -> ModelStore:
        if store.refresh():
            loaded.clear()
            if store.model:
                loaded.labels(store.model.name, str(store.model.version)).set(1)
        reload_errors.set(store.reload_errors)
        return store

    # Liveness: the process is up. It does not depend on a model being loaded.
    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    # Readiness: only ready once a model is loaded, so no traffic arrives before there is a model.
    @app.get("/ready")
    def ready(s: ModelStore = Depends(current)) -> dict[str, str | int]:
        if s.model is None:
            raise HTTPException(status_code=503, detail="No model loaded")
        return {"status": "ready", "model": s.model.name, "version": s.model.version}

    # Scores one request with the live model. Wrong number of features is a 422.
    @app.post("/predict", response_model=PredictOut)
    def predict(body: PredictIn, s: ModelStore = Depends(current)) -> PredictOut:
        model = s.model
        if model is None:
            raise HTTPException(status_code=503, detail="No model loaded")
        if len(body.features) != len(model.weights):
            raise HTTPException(
                status_code=422,
                detail=f"Expected {len(model.weights)} features, got {len(body.features)}",
            )
        predictions.labels(model.name, str(model.version)).inc()
        return PredictOut(
            prediction=model.predict(body.features), model=model.name, version=model.version
        )

    return app


app = create_app()

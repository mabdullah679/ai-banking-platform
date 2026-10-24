from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from prometheus_client import Counter
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError

from common.observability import add_observability, get_logger
from platform_api import auth
from platform_api.config import get_settings
from platform_api.db import Base, engine
from platform_api.routers import health, jobs, models, teams

SERVICE = "platform-api"


# Creates the tables on first start.
@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="ml-platform-api", lifespan=lifespan)
registry = add_observability(app, SERVICE)

# Counts job submissions by team and result, so quota pressure shows up on a dashboard.
app.state.job_counter = Counter(
    "platform_jobs_submitted_total",
    "Job submissions by team and result",
    ["team", "result"],
    registry=registry,
)


# Turns "database is down or too slow" into a clean 503 that tells callers to retry later.
async def database_unavailable(request: Request, exc: Exception) -> JSONResponse:
    get_logger(SERVICE).error(
        "database unavailable",
        extra={"fields": {"error": type(exc).__name__, "path": request.url.path}},
    )
    return JSONResponse(
        status_code=503,
        content={"detail": "Database unavailable, try again later"},
        headers={"Retry-After": "5"},
    )


# Only connection-type errors become 503. Other database errors are bugs and stay 500.
app.add_exception_handler(OperationalError, database_unavailable)
app.add_exception_handler(PoolTimeoutError, database_unavailable)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(teams.router)
app.include_router(jobs.router)
app.include_router(models.router)

# Referenced so a settings error shows up at startup rather than on the first request.
get_settings()

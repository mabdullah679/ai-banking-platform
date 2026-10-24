import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from fastapi import FastAPI, Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
)


class JsonFormatter(logging.Formatter):
    """Turns each log record into one line of JSON so tools can search it."""

    # Builds the JSON line from the record plus any extra fields we attached.
    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, object] = {
            "time": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        entry.update(getattr(record, "fields", {}))
        return json.dumps(entry)


# Returns a logger for one service that prints JSON lines to the console.
def get_logger(service: str) -> logging.Logger:
    logger = logging.getLogger(service)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


# Finds the route pattern (like /jobs/{job_id}) so metrics do not explode in size.
def route_label(request: Request) -> str:
    return getattr(request.scope.get("route"), "path", "unmatched")


# Adds request IDs, JSON access logs, request metrics and a /metrics endpoint to an app.
# Returns the app's own metrics registry so the app can add its own counters to it.
def add_observability(app: FastAPI, service: str) -> CollectorRegistry:
    registry = CollectorRegistry()
    requests_total = Counter(
        "http_requests_total",
        "Total HTTP requests",
        ["method", "path", "status"],
        registry=registry,
    )
    latency = Histogram(
        "http_request_duration_seconds",
        "Request latency in seconds",
        ["method", "path"],
        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
        registry=registry,
    )
    logger = get_logger(service)

    # Runs on every request: assigns a request ID, times it, logs one line, records metrics.
    @app.middleware("http")
    async def observe(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        start = time.perf_counter()
        status = 500  # stays 500 if the request crashes, so crashes are still counted
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            seconds = time.perf_counter() - start
            path = route_label(request)
            requests_total.labels(request.method, path, str(status)).inc()
            latency.labels(request.method, path).observe(seconds)
            fields = {
                "service": service,
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": status,
                "duration_ms": round(seconds * 1000, 2),
                "user": getattr(request.state, "user", None),
                "team": getattr(request.state, "team", None),
            }
            logger.info("request", extra={"fields": fields})

    # Exposes all metrics in the text format that Prometheus scrapes.
    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)

    app.state.metrics_registry = registry
    return registry

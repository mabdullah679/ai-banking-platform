# Slim base image: small download, small attack surface.
FROM python:3.12-slim

# Do not write .pyc files, and print logs immediately instead of buffering them.
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR /srv

# Install dependencies first so Docker can reuse this cached layer when only code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY common ./common
COPY platform_api ./platform_api
COPY model_server ./model_server

# Run as a non-root user. /models is where the model registry files live (a shared volume).
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /models \
    && chown -R appuser /srv /models
USER appuser

EXPOSE 8000

# One image, two programs. This runs the platform API; the model server overrides the command.
CMD ["uvicorn", "platform_api.main:app", "--host", "0.0.0.0", "--port", "8000"]

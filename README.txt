AI-BANKING-PLATFORM (plain version of README.md)

WHAT IT IS
A practice platform for running AI work for many teams: job limits per team, a store of model versions with quick undo, a server that answers with the live model, and alerts based on reliability targets. It is being replaced by an AI banking app on the same infrastructure. What that app must achieve is in docs/vision/VISION.md.

EVERY MERGE HAS A RECORD
Each merge has a detailed technical file in docs/merge-requests named state-of-affairs-at-merge-request plus the number. It says what was proven and what was not. docs/WORKFLOW.md explains the process.

WHAT IS NOT REAL
The login is fake: alice (team-a), bob (team-b) and root (admin), password demo-pass. Jobs are not actually run: the platform writes out the Kubernetes job description and stops.

WHAT YOU NEED
Docker Desktop with Compose, and ports 8000, 8001, 9090 and 3000 free. Python 3.12 only if you run things outside Docker. No cloud account, cluster or database server.

HOW TO RUN
Start everything with: docker compose up --build -d
Then open http://localhost:8000/docs (on Mac use open, on Windows PowerShell use Start-Process, on Command Prompt use start).
Log in through the token endpoint, copy the token, click Authorize. The model server says not ready until a team promotes a model.
docker compose ps lists the four services, docker compose logs -f shows request logs, docker compose down stops everything.
If a port is taken, set API_HOST_PORT, MODEL_HOST_PORT, PROMETHEUS_HOST_PORT or GRAFANA_HOST_PORT to another number before starting. Nothing else changes.

WHAT IT DOES
A job within the team's limits is accepted and gets a Kubernetes job description. A job over a limit is refused and the reply names the limit. Another team's jobs and models look like they do not exist. Models are registered, made live and undone, and the model server follows without a restart. A broken model version is refused and the old one keeps serving. If the database is down, calls get a clean "try again later" and the health check still passes while the ready check fails.

TESTS
31 tests, no server or cloud needed. Run them with Python 3.12 after installing requirements.txt, or inside the python:3.12-slim Docker image. Nine safety rules were broken on purpose and each one made a test fail. GitHub runs the tests on every pull request, along with a check of the alert rules, the Kubernetes files and a Docker build.

DESIGN NOTES
Undoing a model only rewrites a small pointer file, so it takes seconds instead of a redeploy.
Team limits are checked twice: the platform refuses early with a clear reason, and Kubernetes enforces a hard ceiling in case the platform has a bug.

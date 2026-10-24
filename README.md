# ai-banking-platform — ML platform today, AI banking app next

A practice platform for running AI workloads for many teams: job quotas, a model registry with rollback, a model server, and SLO-based alerting. It is being replaced by an AI banking app on the same infrastructure; what that app must achieve is in
[docs/vision/VISION.md](docs/vision/VISION.md).

**Every merge has a full technical record:** `docs/merge-requests/state-of-affairs-at-merge-request-<number>.md`. Start there to see what each change proved and what it did not. The workflow that produces them is in [docs/WORKFLOW.md](docs/WORKFLOW.md).

```
team ──JWT──▶ platform-api (:8000) ──writes current.json──▶ model store ◀──reads── model-server (:8001)
                    │                                                                   │
                    └──────────────── /metrics ──▶ prometheus (:9090) ◀─── /metrics ────┘
                                                        │
                                                        └──▶ grafana (:3000)
```

The identity provider is **not** real: three demo users stand in for it. Jobs are **not** executed: the platform renders the Kubernetes Job and stops there. Everything else runs locally.

## Prerequisites

- Docker Desktop 4.x with Compose v2
- Ports 8000, 8001, 9090 and 3000 free (see below if not)
- Python 3.12, only if you want to run the services or tests outside Docker

No cloud account, Kubernetes cluster or database server is needed.

## Run it

**macOS / Linux (bash, zsh)**

```bash
docker compose up --build -d
open http://localhost:8000/docs
```

**Windows (PowerShell)**

```powershell
docker compose up --build -d
Start-Process http://localhost:8000/docs
```

**Windows (Command Prompt)**

```bat
docker compose up --build -d
start http://localhost:8000/docs
```

Sign in at `POST /token` as `alice` (team-a), `bob` (team-b) or `root` (platform admin), password `demo-pass`, then click **Authorize**. The model server reports not-ready until a team promotes a model.

These are identical on macOS, Linux and Windows:

```bash
docker compose ps              # four services running
docker compose logs -f         # JSON request logs from both services
docker compose down            # stop
```

### If a port is taken

Set `API_HOST_PORT`, `MODEL_HOST_PORT`, `PROMETHEUS_HOST_PORT` or `GRAFANA_HOST_PORT` before starting, for example `GRAFANA_HOST_PORT=3100 docker compose up --build -d` (PowerShell: `$env:GRAFANA_HOST_PORT=3100`; Command Prompt: `set GRAFANA_HOST_PORT=3100`). Containers talk to each other on their internal ports, so nothing else changes.

## What it does

| Action | Expected | Vision criterion |
| --- | --- | --- |
| Submit a job within quota | `201` and a rendered Kubernetes Job in the team's namespace | 8 |
| Submit over quota (CPU, memory, GPU or active jobs) | `409` with the limit that was hit | 9 |
| Read another team's job or model | `404` | 3 |
| Register, promote, roll back a model | model server serves the new version without a restart | 7 |
| Promote a broken model version | old version keeps serving; the refusal is counted | 4 |
| Database down | `503` with `Retry-After`; `/health` stays `200`, `/ready` fails | 5 |

## Endpoints

| Method | Path | Auth |
| --- | --- | --- |
| POST | `/token` | Public (demo login) |
| GET | `/teams/me` | Any valid token |
| POST, GET | `/jobs` | Any valid token (own team only) |
| GET, DELETE | `/jobs/{job_id}` | Any valid token (own team only) |
| PATCH | `/jobs/{job_id}/status` | Platform admin |
| POST, GET | `/models/{name}/versions` | Any valid token (own team only) |
| POST | `/models/{name}/versions/{version}/promote` | Any valid token (own team only) |
| POST | `/models/{name}/rollback` | Any valid token (own team only) |
| POST | `/predict` (model server) | None; internal only, protected by NetworkPolicy |
| GET | `/health`, `/ready`, `/metrics` (both services) | Public |

## Tests

With Python 3.12 on the host:

**macOS / Linux**

```bash
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/pytest -q
```

**Windows (PowerShell)**

```powershell
py -3.12 -m venv .venv; .venv\Scripts\pip install -r requirements.txt; .venv\Scripts\pytest -q
```

**Windows (Command Prompt)**

```bat
py -3.12 -m venv .venv && .venv\Scripts\pip install -r requirements.txt && .venv\Scripts\pytest -q
```

Without Python, Docker only; only the path syntax differs:

**macOS / Linux**

```bash
docker run --rm -v "$PWD":/app -w /app python:3.12-slim sh -c "pip install -q -r requirements.txt && python -m pytest -q"
```

**Windows (PowerShell)**

```powershell
docker run --rm -v "${PWD}:/app" -w /app python:3.12-slim sh -c "pip install -q -r requirements.txt && python -m pytest -q"
```

**Windows (Command Prompt)**

```bat
docker run --rm -v "%cd%:/app" -w /app python:3.12-slim sh -c "pip install -q -r requirements.txt && python -m pytest -q"
```

31 tests: authentication failures, quota admission, team isolation, job status rules, model promote and rollback, the model server following a promotion live, refusal of a broken model, database-down handling, metrics, production refusing dev secrets, and the subnet plan. They run fully offline with an in-memory database. Nine of the guards were broken on purpose and each broke a test. CI runs them on every pull request, plus `promtool` on the alert rules, a Kubernetes render, and a Docker build.

## Layout

| Path | What |
| --- | --- |
| [docs/vision/VISION.md](docs/vision/VISION.md) | What the banking app is for and what must be true for it to succeed |
| [docs/vision/REQUEST_FLOWS.md](docs/vision/REQUEST_FLOWS.md) | Which requests reach which service, and where each bad request is stopped |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Settled decisions and the alternatives rejected |
| [docs/WORKFLOW.md](docs/WORKFLOW.md) | Environments, branches, pull requests, state-of-affairs files |
| [docs/merge-requests/](docs/merge-requests/) | One state-of-affairs file per merge |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Each job-description requirement, its status, and the plan |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | How many teams share one platform: network layout and isolation layers |
| [platform_api/quota.py](platform_api/quota.py) | Per-team quota and admission control |
| [platform_api/registry.py](platform_api/registry.py) | Model versions, promote, rollback |
| [model_server/model.py](model_server/model.py) | Reloads the live model when the pointer changes |
| [common/observability.py](common/observability.py) | Request IDs, JSON logs, metrics for both services |
| [infra/prometheus/rules/slo.yml](infra/prometheus/rules/slo.yml) | SLO recording rules and burn-rate alerts |
| [infra/k8s/](infra/k8s/) | Namespaces, quotas, RBAC, NetworkPolicy, deployments, autoscaling |
| [infra/network/plan.py](infra/network/plan.py) | Subnet plan, checked by tests |

## Notes on two design decisions

**Rollback is a pointer rewrite, not a redeploy.** Redeploying the previous image would also work, but takes minutes and couples model releases to code releases. The registry rewrites a small `current.json`, and the model server reloads within one request, so a bad model is undone in seconds.

**Quota is enforced twice.** The Kubernetes ResourceQuota alone would stop over-use, but the team would only see a pod stuck pending with a cryptic event. The API refuses first with a clear `409` naming the limit, and the ResourceQuota stays as the hard ceiling if the API has a bug.

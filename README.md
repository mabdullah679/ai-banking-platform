# ml-platform

A small platform that gives ML teams self-service infrastructure: submit jobs under per-team quotas, register and promote models with fast rollback, serve the live model, and watch it all through SLO-based alerts.

```
team --JWT--> platform-api (quota check, renders K8s Job, model registry) --writes--> model store (current.json)
                    |                                                                      |
              /metrics                                              model-server (reloads on change, /predict)
                    +--------------------> Prometheus (SLO burn-rate alerts) --> Grafana
```

Not real here: the identity provider (demo users), job execution (the platform renders a Kubernetes Job manifest but never applies it), and the cluster itself.

## Prerequisites

Python 3.12 (newer Pythons are untested here). Docker only for the compose stack, image build and staging script. No cloud account is needed, and nothing needs `kubectl` except the optional manifest render.

## Run it

1. `python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt`
2. `.venv/bin/uvicorn platform_api.main:app --reload` then open http://localhost:8000/docs
3. Log in at `POST /token` as `alice` (team-a), `bob` (team-b) or `root` (platform admin), password `demo-pass`.
4. Full stack with Prometheus and Grafana: `docker compose up --build` (API on 8000, model server on 8001, Prometheus on 9090, Grafana on 3000).

If a port is taken, `docker compose up` fails with "port is already allocated": stop what holds it (`lsof -iTCP:8000 -sTCP:LISTEN`) or change the left-hand number under `ports:` in [compose.yaml](compose.yaml). The staging script expects the default ports.

## What it does

| Action | Result |
|---|---|
| Submit a job within quota | 201 and a rendered Kubernetes Job in the team namespace |
| Submit over quota (cpu, memory, GPU, active jobs) | 409 with the reason |
| Read another team's job or model | 404 |
| Admin reports job status | frees quota when the job ends |
| Register, promote, roll back a model | model server serves the new version without a restart |
| Broken model version promoted | server keeps the old model and counts the error |
| Database down | 503 with Retry-After, `/health` stays 200, `/ready` fails |

## Interface

| Service | Method and path | Auth |
|---|---|---|
| platform-api (8000) | `POST /token` | none (demo users) |
| platform-api | `GET /health`, `GET /ready`, `GET /metrics` | none |
| platform-api | `GET /teams/me` | JWT |
| platform-api | `POST /jobs`, `GET /jobs`, `GET /jobs/{id}`, `DELETE /jobs/{id}` | JWT, own team only |
| platform-api | `PATCH /jobs/{id}/status` | JWT, platform admin only |
| platform-api | `POST /models/{name}/versions`, `GET /models/{name}/versions`, `POST /models/{name}/versions/{n}/promote`, `POST /models/{name}/rollback` | JWT, own team only |
| model-server (8001 in compose) | `POST /predict`, `GET /health`, `GET /ready`, `GET /metrics` | none |

## Tests

`.venv/bin/pytest -q` runs 35 tests with an in-memory database and a temporary model folder. No server, Docker or cloud needed. Nine guards were broken on purpose (quota, team isolation, admin-only, rollback pointer, model-server readiness, bad-version handling, subnet overlap, undersized app subnets, doc drift) and each broke a test; this was re-run on 2026-11-18 by editing each guard and watching a test go red. That re-run also found two untested claims, now covered: the platform API's `/ready` failing when the database is down, and malformed model versions (bad JSON, missing key) being refused.

Staging gate: `scripts/staging.sh` builds the image, starts the compose stack, runs the 7 tests in [staging/test_staging.py](staging/test_staging.py) over HTTP (login, quota, team isolation, admin-only, promote and rollback across the two containers, Prometheus scraping both services with 12 rules loaded, Grafana dashboard provisioned), then tears everything down. Needs Docker and free ports 8000, 8001, 3000, 9090. It does not drive a browser, so what the Grafana dashboard looks like is not covered.

## Layout

| Path | Role |
|---|---|
| [platform_api/](platform_api/) | control plane: auth, quota, runner, registry, routers |
| [model_server/](model_server/) | serves the live model, reloads when the pointer changes |
| [common/observability.py](common/observability.py) | request IDs, JSON logs, metrics shared by both services |
| [infra/prometheus/rules/slo.yml](infra/prometheus/rules/slo.yml) | SLO recording rules and burn-rate alerts |
| [infra/grafana/](infra/grafana/) | provisioned dashboard |
| [infra/k8s/](infra/k8s/) | namespaces, ResourceQuota, RBAC, NetworkPolicy, deployments, HPA, PDB |
| [infra/network/plan.py](infra/network/plan.py) | VPC subnet plan (3 AZs, 3 tiers) with a validator |
| [docs/ROADMAP.md](docs/ROADMAP.md) | every JD requirement, its status here, and the plan to close each gap |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | how many teams share the platform: network layout, isolation layers, cost and failure notes |
| [tests/](tests/) | 35 unit tests |
| [staging/](staging/), [scripts/staging.sh](scripts/staging.sh) | compose-stack tests and the one command that runs them |
| [compose.yaml](compose.yaml), [Dockerfile](Dockerfile), [.github/workflows/ci.yml](.github/workflows/ci.yml) | local stack, image, CI (lint, tests, promtool, kustomize, image build, staging, gitleaks) |
| [CLAUDE.md](CLAUDE.md) | repo-specific instructions for AI coding sessions |

## Design decisions

- **Quota is enforced twice**: the API refuses early with a clear reason, and the Kubernetes ResourceQuota is the hard ceiling.
- **Rollback is a pointer rewrite**, not a redeploy, so it takes seconds.
- **Known gap**: two simultaneous submissions can both pass the quota check. A PostgreSQL row lock on the team would fix it.
- **SQLite is per pod**, so the platform API runs one replica until it moves to PostgreSQL.

## Not verified

- Re-checked 2026-11-18: Prometheus config and all 12 rules pass `promtool check`; `kubectl kustomize` renders 25 objects; the Docker image builds and the compose stack comes up and passes the staging suite (commit and counts are in the pull request).
- Kubernetes manifests were not schema-validated or applied; there is no cluster.
- The VPC and subnets are a validated plan (no overlaps, sized for pods) but nothing is provisioned, and there is no Terraform.
- PostgreSQL, GPU scheduling and a real identity provider are not built. No UI of its own exists; the Grafana dashboard was provisioned and found by API, never looked at in a browser.

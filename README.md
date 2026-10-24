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

Python 3.12. Docker only for the compose stack and image build. No cloud account is needed.

## Run it

1. `python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt`
2. `.venv/bin/uvicorn platform_api.main:app --reload` then open http://localhost:8000/docs
3. Log in at `POST /token` as `alice` (team-a), `bob` (team-b) or `root` (platform admin), password `demo-pass`.
4. Full stack with Prometheus and Grafana: `docker compose up --build`.

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

## Tests

`.venv/bin/pytest -q` runs 31 tests with an in-memory database and a temporary model folder. No server or cloud needed. Nine guards were broken on purpose (quota, team isolation, admin-only, rollback pointer, readiness, bad-version handling, subnet overlap, undersized app subnets, doc drift) and each broke a test.

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
| [compose.yaml](compose.yaml), [Dockerfile](Dockerfile), [.github/workflows/ci.yml](.github/workflows/ci.yml) | local stack, image, CI |

## Design decisions

- **Quota is enforced twice**: the API refuses early with a clear reason, and the Kubernetes ResourceQuota is the hard ceiling.
- **Rollback is a pointer rewrite**, not a redeploy, so it takes seconds.
- **Known gap**: two simultaneous submissions can both pass the quota check. A PostgreSQL row lock on the team would fix it.
- **SQLite is per pod**, so the platform API runs one replica until it moves to PostgreSQL.

## Not verified

(Prometheus config and all 12 rules pass `promtool check`, as of 2026-10-24.)


- Docker image build and the compose stack: Docker Desktop was paused, so neither was run.
- Kubernetes manifests render with `kubectl kustomize` (25 objects) but were not schema-validated or applied; there is no cluster.
- The VPC and subnets are a validated plan (no overlaps, sized for pods) but nothing is provisioned, and there is no Terraform.
- GitHub Actions has not run. PostgreSQL, GPU scheduling and a real identity provider are not built.

# CLAUDE.md

ml-platform (repo name `ai-banking-platform`): FastAPI control plane for ML teams (quotas, jobs, model registry) plus a model server, with Kubernetes manifests, Prometheus rules and a Grafana dashboard. Standing rules for all work live in `~/.claude/CLAUDE.md`; this file only adds what is specific to this repo.

## Commands (all run and verified 2026-11-18)

- Setup: `python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt` (Python 3.12 required; the default `python3` here may be newer)
- Unit tests: `.venv/bin/pytest -q` (35 tests, in-memory SQLite, no server needed)
- Lint: `.venv/bin/ruff check .` (line length 100, config in `pyproject.toml`)
- Prometheus rules: `docker run --rm -v "$PWD/infra/prometheus/rules:/rules" --entrypoint promtool prom/prometheus:v3.5.0 check rules /rules/slo.yml`
- K8s render: `kubectl kustomize infra/k8s` (25 objects)
- Staging gate: `scripts/staging.sh` builds the image, brings up `compose.yaml` under project `mlplatform-staging`, runs `staging/` (7 HTTP tests) against it, then removes containers, volume and images. Needs ports 8000, 8001, 3000, 9090 free.

## Layout

`platform_api/` control plane, `model_server/` serving, `common/` shared observability, `infra/` k8s, prometheus, grafana, VPC plan, `tests/` unit tests, `staging/` compose-stack tests (not collected by plain `pytest`), `docs/` design and workflow.

## Conventions

- Feature branch, PR into `main`; never push to `main`. Branch protection requires the CI check named `test`, so do not rename that job in `.github/workflows/ci.yml`.
- A guard counts only after it was broken on purpose and a test went red (`docs/WORKFLOW.md`).
- Every function has a short plain-language comment above it; match that.
- Keep `README.md` and `README.txt` in step. Counts in them (tests, rules, objects) must be re-checked, not copied.
- Quotas live in two places that must agree: `TEAM_QUOTAS` in `platform_api/quota.py` and `infra/k8s/teams.yaml`.
- `docs/ARCHITECTURE.md` must list every subnet from `infra/network/plan.py` (a test enforces it).

## Do not touch

- Demo credentials and `DEV_JWT_SECRET` in `platform_api/config.py` are intentional dev stand-ins; production mode refuses them. Do not replace them with real secrets.
- Nothing here may provision cloud resources; the VPC plan is a validated plan only.
- `docs/ROADMAP.md` is the owner's job-hunt planning doc; edit only with the owner's say.

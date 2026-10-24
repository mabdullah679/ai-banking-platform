# Roadmap: ml-platform against the job description

Every requirement in the job description, what the project shows for it today, and what closes the gap. The JD text is kept outside the repo, at `kforce-prep/Job_Description.txt`, so it never gets pushed. Interview 1 added that the role leans toward **SRE/DevOps for AI/ML workloads shared by many teams**, with networking (VPC, subnets) in scope.

Status as of 2026-10-24: 31 tests pass, ruff clean, Prometheus config and 12 rules pass `promtool`, Kubernetes manifests render 25 objects. Not a git repository yet. Docker daemon not running.

**Status key:** **Built** = code plus tests that were broken on purpose and went red. **Checked** = validated by a tool but never run live. **Written** = file exists, never validated or run. **Designed** = in docs only. **Missing** = nothing yet.

## Where the project stands, requirement by requirement

| JD requirement | Status | Evidence or gap |
|---|---|---|
| Backend services and APIs for platform and sandbox environments | Built | `platform_api` (jobs, quotas, registry), `model_server` |
| Python, occasional Java | Built / Missing | All Python. No Java at all |
| Containerized workloads on EKS | Written / Checked | Dockerfile never built for this version; manifests render, never applied |
| Connectivity to approved enterprise data sources | **Missing** | The old project had an allowlist and an adapter; ml-platform does not |
| AuthN/AuthZ with enterprise identity | Built (stand-in) | JWT with team and role, team isolation tested. No real IdP (OIDC, JWKS) |
| Logging, monitoring, tracing, alerting, dashboards | Built / Checked / Missing | JSON logs and metrics built; SLO alerts promtool-checked; dashboard written; **tracing missing** |
| Design reviews and recommendations | Designed | `docs/ARCHITECTURE.md`, with tradeoffs and a built-vs-designed table |
| Reliability, scalability, security, performance | Built / Missing | 503 on database loss, quotas, HPA and PDB written. No load test, so no measured p95 |
| Code reviews and testing standards | Built / Written | Tests plus breaking guards on purpose; CI written, never run; no pull-request history |
| Troubleshoot production issues | Missing | No runbooks |
| Documentation, deployment procedures, integration specs | Built / Missing | README, architecture doc; no deploy procedure or runbook |
| Kubernetes and EKS hands-on | Checked | Render only; no cluster |
| Docker | Written | Image not built since the rewrite |
| AWS and cloud-native patterns | Designed | VPC plan validated by tests; nothing provisioned |
| GitHub branching, PRs, reviews | Missing | Not a git repository |
| CI/CD pipelines | Written | `ci.yml` never run; no deploy stage |
| Distributed systems, microservices, event-driven | Built / Missing | Two services talking through a shared store; **no queue or events** |
| Identity products (Keycloak, Entra ID, OIDC) (preferred) | Missing | Fake login only |
| Prometheus, Grafana, OpenTelemetry (preferred) | Checked / Missing | Prometheus checked, Grafana unrendered, OpenTelemetry missing |
| Terraform (preferred) | Missing | Terraform 1.9.8 is installed, no code |
| Enterprise databases, APIs, data platforms (preferred) | Missing | SQLite only |
| Regulated or security-conscious environments (preferred) | Built (partly) | Access log records user and team, production refuses dev secrets, cross-team reads return 404 |
| AI, ML, data platforms (preferred) | Built | Job admission, model registry, promote and rollback, serving |

## The plan

Every item runs locally and costs nothing. Anything that touches a cloud account or GitHub is marked **(needs your yes)**, per the standing rule.

### Phase 0: housekeeping (about 15 minutes)

| Item | Done when |
|---|---|
| `git init`, `.gitignore` check, first commit | `git log` shows the commit; `secrets.local` and `deploy/` from the archive are not in it |
| Retire the stale `Project_Report.txt` (it describes the old project) | Moved to `archive/` |

### Phase 1: prove what is already written (about 1 hour, no new features)

| Item | Closes | Done when |
|---|---|---|
| Start Docker; build the image; `docker compose up` | Docker | Both services answer `/ready`; Prometheus shows both targets up; Grafana dashboard renders, confirmed with a screenshot |
| Local cluster with kind (install it) plus a NetworkPolicy-capable CNI (Calico) and metrics-server | Kubernetes hands-on | Manifests apply; pods pass probes; a pod in team-b cannot reach team-a, shown with a failed connection; HPA reads CPU |
| Push to GitHub and run CI **(needs your yes)** | GitHub, CI/CD | Green run on a pull request; branch protection on `main` |

### Phase 2: close the JD gaps, in interview-value order

| # | Item | Closes | Done when |
|---|---|---|---|
| 2a | OpenTelemetry tracing across platform API, model server and database | Tracing (explicit JD line) | One request shows as one trace spanning both services; logs carry the trace ID |
| 2b | **Approved data-source connectors**: per-team allowlist of sources, adapter class, credentials from the environment, timeouts, audit log of who read what | Core JD responsibility and "Success: integrates new data sources" | Unapproved source returns 404; another team's source returns 404; slow source returns 503 inside the timeout; each guard broken on purpose |
| 2c | Real identity: Keycloak in compose, RS256 tokens verified against its public keys (JWKS) | Enterprise identity (preferred) | Keycloak-issued token works; tampered or wrong-audience token gets 401; the fake login is removed |
| 2d | PostgreSQL plus migrations (Alembic); fix the quota race with a row lock | Enterprise databases; known gap | Two simultaneous submissions cannot both pass the quota (test proves it); migrations run up and down |
| 2e | Event-driven job execution: queue plus a worker that turns queued jobs into real Kubernetes Jobs on kind | Event-driven, distributed systems | Submitting a job creates a pod in the team namespace; quota frees when it finishes |
| 2f | Runbooks: "model server not ready", "database down", "team hitting quota", "SLO fast burn" | Troubleshooting, deployment procedures | Each runbook was followed once against the local stack |

### Phase 3: stretch

| Item | Closes | Done when |
|---|---|---|
| Terraform for the VPC plan: `terraform validate` and `plan` only, **apply needs your yes** | Terraform, AWS patterns | `validate` passes; CIDRs come from the same plan the tests check |
| Load test (k6 or Locust) against the SLO | Performance | Measured p95 under a stated load, recorded in the README |
| Small Java (Spring Boot) client or service calling the model server | Occasional Java | Built with Maven 3.9 (installed), tested, in CI |
| Canary or shadow model rollout | Safe ML deploys | A new version takes a slice of traffic before full promotion |

## Before interview 2

If time is short, do these and stop: Phase 0, Phase 1's Docker line, 2a (tracing) and 2b (data sources). That covers the two explicit JD responsibilities that are missing and turns "written" into "run" for Docker.

ML-PLATFORM (plain version of README.md)

WHAT IT IS
A small platform that gives machine learning teams self-service infrastructure. A team logs in, submits training jobs under a quota, registers and promotes models, and can roll back a bad model in seconds. A separate model server serves whichever version is live. Prometheus and Grafana files watch reliability.

WHAT IS NOT REAL
The login is fake (alice, bob and root, password demo-pass). Jobs are not actually run: the platform writes out the Kubernetes job description but never applies it. There is no cluster.

HOW TO RUN
You need Python 3.12. Create a virtual environment, install requirements.txt, then start with uvicorn platform_api.main:app and open http://localhost:8000/docs. The full stack with Prometheus and Grafana needs Docker: docker compose up --build.

WHAT IT DOES
Jobs within quota are accepted and get a Kubernetes job description. Jobs over quota are refused with the reason. One team cannot see another team's jobs or models. Models are registered, promoted and rolled back, and the model server follows without a restart. A broken model version is refused and the old one keeps serving. If the database is down, calls get a clean 503 and the health check still passes while the ready check fails.

TESTS
31 tests, no server or cloud needed. Nine rules were broken on purpose, including the network plan checks, and each one made a test fail.

NETWORK AND TEAM SHARING
The file docs/ARCHITECTURE.md explains how many teams share one platform: one network split into public, application and database layers across three zones, with layers of isolation between teams. The subnet numbers are checked by a test so the document cannot drift from the code.

KNOWN GAP
Two jobs submitted at the same instant can both pass the quota check. A database row lock would fix it.

NOT CHECKED
The Docker image and the Docker stack were not run because Docker Desktop was paused. The Prometheus alert rules now pass Prometheus's own checker (promtool), as of 2026-10-24. The Kubernetes files produce 25 objects when rendered but were never checked against a cluster, because there is none. The network design (subnets, security groups) is a checked plan only: nothing is built in AWS and there is no Terraform. GitHub Actions has not run. PostgreSQL, GPU scheduling and a real login system are not built.

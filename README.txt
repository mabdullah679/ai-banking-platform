ML-PLATFORM (plain version of README.md)

WHAT IT IS
A small platform that gives machine learning teams self-service infrastructure. A team logs in, submits training jobs under a quota, registers and promotes models, and can roll back a bad model in seconds. A separate model server serves whichever version is live. Prometheus and Grafana files watch reliability. The GitHub repository is named ai-banking-platform, but nothing in it is about banking.

WHAT IS NOT REAL
The login is fake (alice, bob and root, password demo-pass). Jobs are not actually run: the platform writes out the Kubernetes job description but never applies it. There is no cluster.

WHAT YOU NEED
Python 3.12. Docker only for the full stack, the image build and the staging script. No cloud account.

HOW TO RUN
Create a virtual environment with python3.12, install requirements.txt, then start with uvicorn platform_api.main:app and open http://localhost:8000/docs. Log in at /token as alice (team-a), bob (team-b) or root (platform admin) with password demo-pass. For the full stack with Prometheus and Grafana run docker compose up --build. That uses port 8000 for the API, 8001 for the model server, 9090 for Prometheus and 3000 for Grafana. If one of those ports is already used, Docker says the port is already allocated: stop the program holding it, or change the left-hand number under ports in compose.yaml.

WHAT IT DOES
Jobs within quota are accepted and get a Kubernetes job description. Jobs over quota are refused with the reason. One team cannot see another team's jobs or models. Only the root admin can report job progress. Models are registered, promoted and rolled back, and the model server follows without a restart. A broken model version is refused and the old one keeps serving. If the database is down, calls get a clean 503 and the health check still passes while the ready check fails.

TESTS
35 quick tests, no server, Docker or cloud needed. Nine rules were deliberately broken (quota, team isolation, admin-only, rollback, model server readiness, bad model versions, overlapping subnets, too-small app subnets, and the architecture doc drifting from the code) and each one made a test fail. This was repeated on 2026-11-18. That check also found two claims nobody had tested: the API's ready check failing when the database is down, and corrupted model files being refused. Both now have tests.

STAGING CHECK
One command, scripts/staging.sh, builds the Docker image, starts the whole stack, runs 7 tests against it over the network, and removes everything afterwards. The 7 tests cover login, quota limits, team isolation, admin-only actions, promote and rollback reaching the model server in the other container, Prometheus watching both services with all 12 alert rules loaded, and Grafana having its dashboard. It does not open a browser, so how the dashboard looks was never checked.

NETWORK AND TEAM SHARING
The file docs/ARCHITECTURE.md explains how many teams share one platform: one network split into public, application and database layers across three zones, with layers of isolation between teams. The subnet numbers are checked by a test so the document cannot drift from the code.

KNOWN GAP
Two jobs submitted at the same instant can both pass the quota check. A database row lock would fix it. The API also runs as a single copy because its database is a file inside each container.

NOT CHECKED
Checked again on 2026-11-18: the Prometheus alert rules pass Prometheus's own checker (12 rules), the Kubernetes files produce 25 objects when rendered, and the Docker image and stack build and pass the staging check. Not checked: the Kubernetes files were never validated against a cluster because there is none. The network design (subnets, security groups) is a checked plan only: nothing is built in AWS and there is no Terraform. PostgreSQL, GPU scheduling and a real login system are not built.

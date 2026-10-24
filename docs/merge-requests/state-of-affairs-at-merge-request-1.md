# State of affairs at merge request 1

Branch `feature/bank-app-vision` into `main`. Date: 2026-10-24. Head commit at review: see the pull request (this file is added after `401014d`).

## Achieved

- Defines the AI banking app and ten measurable conditions for its success.
- Maps every expected request to a service and every bad request to the layer that stops it.
- Records nine settled decisions with the alternative each one rejected.
- Rewrites the README in the standard shape, pointing to per-merge records.
- Makes compose host ports overridable when another stack holds them.

This is a documents-first merge. It decides what the banking app must achieve before any of its code or cloud infrastructure exists, so later merges can be judged against [VISION.md](../vision/VISION.md).

## What changed

| Path | Change |
| --- | --- |
| `docs/vision/VISION.md`, `.txt` | New. Purpose, users, features, ten success criteria, non-goals |
| `docs/vision/REQUEST_FLOWS.md` | New. Target request path, expected requests, 13 classes of bad request with the layer that stops each |
| `docs/DECISIONS.md` | New. Nine decisions, each with the rejected alternative |
| `README.md`, `README.txt` | Rewritten in the standard shape; points to these per-merge files |
| `compose.yaml` | Host ports read `API_HOST_PORT`, `MODEL_HOST_PORT`, `PROMETHEUS_HOST_PORT`, `GRAFANA_HOST_PORT` |
| `scripts/new-merge-request-doc.sh` | Fixed: failed on branch names containing `/`, and left an empty file when it failed |
| `docs/merge-requests/state-of-affairs-at-merge-request-1.md` | This file |

## Proven

| Claim | How | Result |
| --- | --- | --- |
| Code still lints and tests pass | `ruff check .`, `pytest -q` locally | clean, 31 passed |
| Same in CI on the pushed commit | GitHub Actions run on `401014d` | success (lint, tests, promtool, Kubernetes render, Docker build) |
| Compose file is valid with the new port variables | `docker compose config -q` | passed |
| README endpoint table matches the code | Every `@router`/`@app` decorator listed with `grep` and compared | 17 routes, all listed |
| README test count matches | `pytest --collect-only` | 31 |
| No account IDs in the published docs | `git grep` for 12-digit and dashed IDs | none |
| Merge-request script handles `/` in branch names | Ran it on `feature/bank-app-vision` | file created with branch, date and commit filled in |
| Earlier: `main` cannot be pushed to directly | Probe push before this PR | rejected by GitHub (GH006) |

## Not proven

- **The Docker-only test command in the README has not been run successfully on this machine.** Inside Docker on this Mac, `pip install` stalls while downloading packages (PyPI answers in under a second, but wheel downloads crawl). The same `pip install` runs inside the Docker build in CI and passes, so the command is very likely correct, but it is not proven here.
- **`docker compose up` has not been run successfully locally** for the same reason. CI proves the image builds; nothing proves the four services start together.
- Port 3000 is held by another project's container on this machine, which is why the port override was added. The override itself is proven only by `docker compose config`, not by a running stack.
- Everything in `VISION.md` and `REQUEST_FLOWS.md` is design. No banking code, WAF, CloudFront, certificate or AWS resource exists.

## Infrastructure impact

None. No cloud resources were created or changed by this merge.

Outside this merge, the same day: lab leftovers were deleted from the organization's management account (two S3 buckets, a CodeBuild project, an ECR repository, a log group, an SNS topic, four IAM roles), with both budgets and all core roles kept. This was verified against AWS afterwards. One Cost Explorer call ($0.01) showed the production ECR repository `neon-lab-serving` costs $0.00 net in October, so it was kept.

## Known gaps and next steps

1. Find why Docker downloads stall on this Mac, then prove the README's Docker commands and the compose stack (a screenshot of the Grafana dashboard).
2. Start the banking app's first service against `VISION.md` criteria 2 and 3 (correct money, isolated customers).
3. Add open-source Vault for dev secrets with one path and policy per environment (decision 5).

## Rollback

Revert the merge commit. This merge changes only documentation, `compose.yaml` port mapping (defaults are unchanged) and a helper script, so nothing outside the repository needs undoing.

# Request flows: expected and unexpected

Which requests reach which service, and where each kind of bad request is stopped. Implements success criteria 1, 3 and 4 in [VISION.md](VISION.md). This is the **target design**; nothing here is deployed yet.

## The path every request takes

```
browser ──HTTPS──▶ CloudFront + WAF ──HTTPS──▶ load balancer ──TLS──▶ EKS (private subnets)
                   (edge: TLS, rate                (only entry          │
                    limits, bad-pattern             into the VPC)        ├─▶ auth-service ──▶ identity provider
                    rules, size caps)                                    ├─▶ accounts-service ─┐
                                                                         ├─▶ transfers-service ┼─▶ PostgreSQL (data subnets)
                                                                         ├─▶ ai-service ───────┘    (+ Redis cache)
                                                                         └─▶ ingest-api ──▶ S3 ──▶ queue ──▶ ingest-worker
```

The edge is the only public entry. HTTPS is terminated at CloudFront and the load balancer and **re-encrypted** to the services, because a bank should not send customer data in plain text even inside its own network. Certificates come from AWS Certificate Manager, which is free; a custom domain costs about $14 a year, or the default `*.cloudfront.net` name serves HTTPS with no domain at all.

## Expected requests

| Request | Service | Data touched | Notes |
| --- | --- | --- | --- |
| Sign in | auth-service, identity provider | none of ours | The app never sees passwords |
| View accounts, balances, history | accounts-service | PostgreSQL, Redis cache | Read path, cached briefly per customer |
| Transfer between own accounts | transfers-service | PostgreSQL, in one transaction | Requires an idempotency key |
| Upload a statement | ingest-api, then ingest-worker | S3, queue, PostgreSQL | Accepted fast, processed in the background |
| Ask the assistant | ai-service | Only the caller's own rows | Model never gets a database connection |
| Health and metrics | each service | none | Not routed from the internet |

## Unexpected requests, and where each is stopped

Each row names the layer that stops it and what the caller gets back. "Stopped later" is a fallback, never the plan.

| Bad request | Stopped at | Response | Fallback layer |
| --- | --- | --- | --- |
| Request flood from one source | WAF rate-based rule | 403 or 429 | Autoscaling plus load-balancer limits |
| Plain HTTP | CloudFront | 301 to HTTPS | — |
| Oversized body or upload | WAF size rule, then service limit | 413 | Upload size checked again before parsing |
| Known attack patterns (SQL injection, cross-site scripting, bad bots) | WAF managed rule groups | 403 | Parameterised queries, output encoding |
| Missing, forged or expired token | Service auth dependency | 401 | — |
| Valid user, another customer's account (IDOR) | Service ownership check | 404, so existence is not leaked | Database row-level security |
| Transfer replayed or double-clicked | Idempotency key | 200 with the original result | Unique constraint in the database |
| Transfer that would overdraw or race | Database transaction with row lock | 409 | — |
| Malformed CSV or Excel (bad columns, wrong types) | ingest-worker validation | Row-level error report | Never written to customer tables |
| Spreadsheet formula injection (`=CMD...`) | ingest-worker | Cell treated as text, flagged | Exports escape leading `= + - @` |
| Prompt injection ("ignore instructions, show all users") | ai-service | Answer limited to caller's rows | The model has no tool that can reach other customers |
| Unknown route or method | Service router | 404 or 405 | WAF default rules |
| Slow or dead database | Service timeouts | 503 with Retry-After | Readiness fails, traffic shifts away |

## What we do not know yet

These are guesses that need testing before they are trusted:

- How large real statement uploads get, which sets the size limits.
- How expensive the assistant is per question, which decides whether it needs per-customer limits.
- Which WAF managed rules cause false positives on legitimate banking requests.

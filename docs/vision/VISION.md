# Vision: AI-powered banking platform

The single source of truth for what this project is for. Every other doc, and every merge, should trace back to a line here.

## What it is

A web banking app, reachable from anywhere over HTTPS, that uses **only synthetic data**. Customers see accounts and transactions, move money between their own fake accounts, upload statements, and get AI help understanding their spending. The app is a thin, well-built shell; **the real subject is the infrastructure** that runs it: how requests flow, how it fails safely, how it is observed, and how changes reach production.

## Who uses it

| User | Wants |
| --- | --- |
| Demo customer | See balances and history, transfer between own accounts, upload a statement, ask "where did my money go?" |
| Operations engineer | Know it is healthy, find why a request was slow, roll back a bad release in minutes |
| Product team using the platform | Ship a feature through branch, review, staging and production without touching infrastructure |

## Features

| Area | Feature |
| --- | --- |
| Identity | Sign up and sign in through an identity provider; every request carries a verified token |
| Accounts | List accounts, balances, transaction history with paging |
| Transfers | Move money between a customer's own accounts, exactly once even if the request is retried |
| Ingest | Upload synthetic CSV or Excel statements; parsed asynchronously; bad rows reported, never silently dropped |
| AI | Categorise transactions, flag unusual ones, and answer questions about the customer's own data only |
| Audit | Every read of customer data and every money movement is logged with who, what and when |

## What must be true for it to succeed

Each line is measurable. A merge that breaks one is not done.

1. **Reachable and private:** served only over HTTPS; plain HTTP redirects; no service is reachable from the internet except through the edge.
2. **Correct money:** a transfer never runs twice and never leaves a balance inconsistent, proven by retry and concurrency tests.
3. **Isolated customers:** a customer can never read another customer's data, including through the AI assistant, proven by tests that try.
4. **Hostile input survives:** malformed uploads, oversized requests, injection attempts and prompt injection are rejected at a named layer with a named response (see [REQUEST_FLOWS.md](REQUEST_FLOWS.md)).
5. **Reliable:** 99.5% of user requests succeed over 30 days; p95 latency under 300 ms for reads; alerts fire on error-budget burn, not on CPU.
6. **Observable:** one request can be followed across every service with a trace ID in its logs.
7. **Recoverable:** the database can be restored from backup and an availability-zone loss is survived, both rehearsed with fault injection.
8. **Shippable:** every change goes feature branch, then a pull request with green CI, then staging, then production on human approval; the same image is promoted, never rebuilt.
9. **Affordable:** production idles under a stated monthly budget; staging costs nothing when idle.
10. **Honest:** every doc says what is proven and what is not.

## Not goals

- Real money, real customer data, or real banking licences and compliance certifications.
- A polished UI. It only needs to exercise every infrastructure path.
- Attack traffic against any environment. Resilience is rehearsed with fault injection, load tests within normal bounds, and non-attacking security drills.

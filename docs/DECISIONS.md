# Decisions

Settled choices, newest last. Each says what was decided, the obvious alternative, and why the alternative loses here. Change a decision by adding a new entry, not by editing an old one.

| # | Date | Decision | Alternative rejected, and why |
| --- | --- | --- | --- |
| 1 | 2026-10-24 | Environments (staging, production) live in **one AWS account**, separated by unpeered VPCs, `Environment` tags and per-environment IAM roles | One account per environment is stronger isolation, but costs more setup and operations for a one-person practice platform. Shared-IAM risk is documented in [WORKFLOW.md](WORKFLOW.md) |
| 2 | 2026-10-24 | Staging and production in the **same region** | A second region adds no permission isolation (IAM is global) and adds latency and transfer cost; it only pays off as a deliberate disaster-recovery rehearsal |
| 3 | 2026-10-24 | Staging is **on demand**: created by the pipeline, torn down when tests are confirmed done or after 30 minutes, whichever comes first, within about $10 a month | Always-on staging that mirrors EKS costs roughly $120+ a month at published rates; the always-free tier cannot run EKS |
| 4 | 2026-10-24 | Repository is **public**; secrets are never committed; account IDs are kept out of tracked files and history | Private hides the work from reviewers. Public means every commit must be safe to publish, which CI and review enforce |
| 5 | 2026-10-24 | Dev secrets live in **open-source HashiCorp Vault** with one path and one policy per environment (`dev/`, `staging/`) | Vault namespaces are an Enterprise (paid) feature; separate paths with separate policies give the same separation for free |
| 6 | 2026-10-24 | `main` is protected: pull request required, the `test` check must pass, admins included, no force pushes. **Zero required approvals** | GitHub does not let an author approve their own pull request; with one owner, requiring an approval would block every merge. The human merge click is the review |
| 7 | 2026-10-24 | The **AI banking app replaces ml-platform** in this repository | Keeping both would split attention; ml-platform remains in git history |
| 8 | 2026-10-24 | **No attack traffic** against any environment; resilience is rehearsed with AWS Fault Injection Service, load tests within normal bounds, and non-attacking security drills (GuardDuty sample findings, WAF in count mode, tabletop exercises) | Simulated DDoS is only permitted through AWS-approved testing partners, and attack traffic against a live account risks more than the app |
| 9 | 2026-10-24 | HTTPS terminates at the edge and is **re-encrypted** to the services | Plain HTTP inside the VPC is cheaper and common, but a bank should not move customer data unencrypted even internally |

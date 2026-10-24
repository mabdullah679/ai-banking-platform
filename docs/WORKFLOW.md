# Workflow: from a feature branch to production

## Environments

All cloud environments live in **one AWS account** (production, region `ap-southeast-2`), separated by network and tags rather than by account.

| Environment | Where | Who changes it | How code gets there |
| --- | --- | --- | --- |
| dev | your laptop (Docker, kind) | the agent, freely | commits on a feature branch |
| staging | its own VPC in the account, tagged `Environment=staging` — **not set up yet** | the pipeline only | after merge to `main` |
| production | its own VPC in the account, tagged `Environment=production` | the pipeline only, after a human approves | the **same image** staging tested, promoted by its digest |

The VPCs are never peered, so staging traffic cannot reach production. "Promotion" means deploying the exact image that passed staging with production's config; nothing is rebuilt. The pipeline reaches AWS through an OIDC role, so no long-lived keys exist anywhere.

**The tradeoff we accepted:** separate VPCs isolate *traffic*, but IAM, service quotas and billing are shared by the whole account. A staging role with broad permissions could change production. We reduce that with one IAM role per environment whose permissions are limited by the `Environment` tag, separate Terraform state per environment, and tag-based cost reports. Separate accounts would remove the risk entirely; we chose simplicity.

## Branches and merges

1. The agent works on `feature/<short-name>` and commits small, working steps.
2. At a milestone it opens a pull request. The description has at most 5 one-sentence bullets.
3. It runs `scripts/new-merge-request-doc.sh <pr-number>` and fills in the state-of-affairs file: the in-depth technical record of that merge.
4. A human reviews and merges. The agent never merges its own pull request.
5. `main` is protected: CI must pass and one approval is required.

## Rules that apply to every merge

- A guard is only trusted after it was broken on purpose and a test went red.
- Anything not run goes under "Not proven", never under "Proven".
- No cloud resource is created without a recorded yes for that exact plan, and every one is torn down and verified when it is no longer needed.

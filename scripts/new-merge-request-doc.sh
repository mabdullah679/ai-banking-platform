#!/usr/bin/env bash
# Creates docs/merge-requests/state-of-affairs-at-merge-request-<number>.md from the template.
# Usage: scripts/new-merge-request-doc.sh <pull request number>
set -euo pipefail
n="${1:?usage: $0 <pull request number>}"
out="docs/merge-requests/state-of-affairs-at-merge-request-${n}.md"
[ -e "$out" ] && { echo "already exists: $out" >&2; exit 1; }
sed -e "s/<number>/${n}/g" \
    -e "s/<branch>/$(git branch --show-current)/" \
    -e "s/<YYYY-MM-DD>/$(date +%F)/" \
    -e "s/<sha>/$(git rev-parse --short HEAD)/" \
    docs/merge-requests/TEMPLATE.md > "$out"
echo "created $out"

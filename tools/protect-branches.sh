#!/usr/bin/env bash
# Protect main and develop: changes only through pull requests whose required
# checks (the CI gates) are green and whose branch is up to date with its base.
# tools/release.sh merges with merge commits, so a linear history is NOT required.
#
# Usage: tools/protect-branches.sh     (normal user, gh logged in; run again after changes)
set -euo pipefail

BODY='{"required_status_checks":{"strict":true,"contexts":["gates (3.12)","gates (3.14)"]},
"enforce_admins":false,"required_pull_request_reviews":null,"restrictions":null,
"required_linear_history":false,"allow_force_pushes":false,"allow_deletions":false}'
for branch in main develop; do
    gh api -X PUT "repos/{owner}/{repo}/branches/$branch/protection" --input - <<<"$BODY" >/dev/null
    echo "protected: $branch"
done
gh api -X PATCH "repos/{owner}/{repo}" -F allow_merge_commit=true >/dev/null
echo "merge commits allowed"

#!/usr/bin/env bash
# Require the CI gates and a linear history on main and develop.
# Run once after the repository became public (normal user, gh login).
set -euo pipefail

BODY='{"required_status_checks":{"strict":false,"contexts":["gates (3.12)","gates (3.14)"]},
"enforce_admins":false,"required_pull_request_reviews":null,"restrictions":null,
"required_linear_history":true,"allow_force_pushes":false,"allow_deletions":false}'
for branch in main develop; do
    gh api -X PUT "repos/{owner}/{repo}/branches/$branch/protection" --input - <<<"$BODY" >/dev/null
    echo "protected: $branch"
done

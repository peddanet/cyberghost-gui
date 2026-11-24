#!/usr/bin/env bash
# Quality gates. The same script runs locally (pre-push hook) and in CI.
#
#   0. privacy  no locally listed term in files, paths, commit texts or identities
#   1. shell    shellcheck over every shell script
#   2. format   pycodestyle, maximum line length 100
#   3. lint     pylint incl. Google-style docstring checks, score 10.00/10
#   4. types    mypy
#   5. security bandit
#   6. tests    pytest with branch coverage of at least 90 %
#
# Usage: tools/check.sh [--fast]     --fast skips the test gate
# Runs as a normal user. The project venv is activated automatically.

set -euo pipefail
cd "$(dirname "$0")/.."

FAST=0
[[ "${1:-}" == "--fast" ]] && FAST=1

if [[ -z "${VIRTUAL_ENV:-}" && -f .venv/bin/activate ]]; then
    # shellcheck disable=SC1091  # path chosen at run time
    source .venv/bin/activate
    echo "venv: .venv (activated for this check)"
fi

gate() {
    local name="$1"; shift
    printf '\n=== %-8s %s\n' "$name" "$*"
    "$@"
}

for tool in pycodestyle pylint mypy bandit; do
    command -v "$tool" >/dev/null || {
        echo "missing tool: $tool  ->  .venv/bin/pip install -r requirements-dev.txt" >&2
        exit 2
    }
done
command -v shellcheck >/dev/null || {
    echo "missing tool: shellcheck  ->  sudo apt install shellcheck" >&2
    exit 2
}

gate privacy  python3 tools/privacy_scan.py
gate shell    shellcheck install.sh tools/*.sh .githooks/pre-push data/90-cyberghost-gui-ipv6
gate format   pycodestyle --max-line-length=100 src tests tools
gate lint     pylint --fail-under=10 src tests tools
gate types    mypy
gate security bandit -q -c pyproject.toml -r src
if (( FAST == 0 )); then
    run=(python3 -m pytest -q -p no:cacheprovider --cov=cghostgui --cov-report=term)
    # a virtual display keeps test windows off the desktop
    if command -v xvfb-run >/dev/null; then
        run=(xvfb-run -a "${run[@]}")
    fi
    GSK_RENDERER=cairo GTK_A11Y=none gate tests "${run[@]}"
fi

printf '\nAll quality gates passed.\n'

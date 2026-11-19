#!/usr/bin/env bash
# Quality gates. The same script runs locally (pre-push hook) and in CI.
#
#   0. privacy  no locally listed term in files, paths or commit texts
#   1. format   pycodestyle, maximum line length 100
#   2. lint     pylint incl. Google-style docstring checks, score 10.00/10
#   3. types    mypy
#   4. security bandit
#   5. tests    pytest with branch coverage of at least 90 %
#
# Usage: tools/check.sh [--fast]     --fast skips the test gate
# Runs as a normal user. The project venv is activated automatically.

set -euo pipefail
cd "$(dirname "$0")/.."

FAST=0
[[ "${1:-}" == "--fast" ]] && FAST=1

if [[ -z "${VIRTUAL_ENV:-}" && -z "${CI:-}" ]]; then
    if [[ ! -f .venv/bin/activate ]]; then
        echo "no .venv: python3 -m venv --system-site-packages .venv" \
             "&& source .venv/bin/activate && pip install -r requirements-dev.txt" >&2
        exit 2
    fi
    # shellcheck disable=SC1091
    source .venv/bin/activate
fi

gate() {
    local name="$1"; shift
    printf '\n=== %-8s %s\n' "$name" "$*"
    "$@"
}

for tool in pycodestyle pylint mypy bandit; do
    command -v "$tool" >/dev/null || {
        echo "missing tool: $tool  ->  pip install -r requirements-dev.txt" >&2
        exit 2
    }
done

gate privacy  python3 tools/privacy_scan.py
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

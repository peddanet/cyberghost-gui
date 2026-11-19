# Contributing

## Branching

History is strictly linear: no merge commits, locally or on GitHub.

| Branch | Purpose | Integrated by |
|---|---|---|
| `main` | releases, every release has an annotated tag `vX.Y.Z` | fast-forward from `develop` |
| `develop` | finished work | fast-forward from a rebased branch |
| `feature/*`, `release/*` | one change | pull request for the CI run, then fast-forward |

The merge buttons on GitHub are not used, because they write new commits.

## Development environment

Always work inside the project venv (normal user):

~~~bash
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
git config core.hooksPath .githooks
tools/check.sh
~~~

`tools/check.sh` activates `.venv` itself when no environment is active.

## Quality gates

| Gate | Tool | Pass criterion |
|---|---|---|
| privacy | `tools/privacy_scan.py` | no locally listed term in files, paths, commit texts |
| format | pycodestyle | no finding, line length 100 |
| lint | pylint | 10.00/10 including Google-style docstrings |
| types | mypy | no error |
| security | bandit | no finding |
| tests | pytest, coverage | all pass, no resource leak, branch coverage at least 90 % |

The same script runs in the pre-push hook and in CI (Python 3.12 and 3.14).

## Releases and updates

A release archive `cyberghost-gui-X.Y.Z-patch.tar.gz` contains `git format-patch`
files. `update/apply-release.sh` applies it, runs the gates, waits for CI,
fast-forwards `develop` and `main`, tags the release and calls `install.sh`.
`install.sh` always works inside the installed venv and then tells a running
application to switch to the new release. The VPN connection stays up.

## Coding rules

1. English for code, comments, docstrings, commit texts and documentation; the
   user interface is German.
2. External programs are started with argument lists, never through a shell.
3. Passwords never appear on a command line or in a log.
4. Nothing is deleted without a request; replaced files move to `geloescht`.
5. User guide and developer guide are updated with every change.
6. The repository holds no personal names, hosts, addresses or vendor files.

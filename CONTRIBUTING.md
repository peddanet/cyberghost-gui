# Contributing

## Branching (git-flow)

| Branch | From | Into | Purpose |
|---|---|---|---|
| `main` | - | - | releases only; every release has an annotated tag `vX.Y.Z` |
| `develop` | `main` | `main` | integration of finished features |
| `feature/<name>` | `develop` | `develop` | one change |
| `hotfix/<name>` | `main` | `main` and `develop` | urgent fix of the released version, always a patch |

`main` and `develop` are protected (`tools/protect-branches.sh`): they change only
through pull requests whose required checks `gates (3.12)` and `gates (3.14)` are
green. Nobody commits on them directly; `tools/release.sh` does all merges.

## Development environment

Once per clone (normal user; writes only into the project folder):

~~~bash
cd ~/Projects/cyberghost-gui && python3 -m venv --system-site-packages .venv && .venv/bin/pip install -r requirements-dev.txt && git config core.hooksPath .githooks
~~~

`--system-site-packages` makes the distribution's PyGObject visible. The gate
`shell` needs shellcheck once: `sudo apt install shellcheck` (sudo because apt
writes to `/usr`). `tools/check.sh` activates `.venv` by itself.

## Quality gates

| Gate | Tool | Pass criterion |
|---|---|---|
| privacy | `tools/privacy_scan.py` | no locally listed term in files, paths, commit texts, author/committer/tagger |
| shell | shellcheck | no finding in any shell script |
| format | pycodestyle | no finding, line length 100 |
| lint | pylint | 10.00/10 including Google-style docstrings |
| types | mypy | no error |
| security | bandit | no finding |
| tests | pytest, coverage | all pass, no resource leak, branch coverage at least 90 % |

The same script runs in the pre-push hook and in CI (Python 3.12 and 3.14).

## Integrating and releasing (`tools/release.sh`)

All steps run as a normal user. `tools/release.sh` looks at the current
branch and does what fits it; the quality gates always run before anything
is merged, and nothing is pushed or installed without a question.

| Current branch   | What the script does                                                   |
|------------------|------------------------------------------------------------------------|
| `feature/<name>` | rebase onto `develop`, gates, merge `--no-ff` into `develop`, then asks "Release jetzt bauen?" |
| `develop`        | release of the collected features: asks the part (default minor) and the release message |
| `hotfix/<name>`  | patch release into `main` and back into `develop`                       |
| `main`           | refused                                                                |

A release computes the version from the newest tag on `main` and the part
(`patch` 1.1.2 -> 1.1.3, `minor` -> 1.2.0, `major` -> 2.0.0; never edit
`__version__` by hand), sets the CHANGELOG heading, runs the gates, merges
into `main` with the message `cyberghost-gui X.Y.Z: <release message>`, tags
`vX.Y.Z` with the same annotation, brings `develop` up to `main`, checks
with `tools/same-code.sh` that `main`, `develop` and the tag are
bit-identical and then asks before the push and before `./install.sh vX.Y.Z`.

### Feature (normal case)

~~~bash
cd ~/Projects/cyberghost-gui && source .venv/bin/activate
git switch develop && git pull --ff-only && git switch -c feature/<short-name>
# ... change code and tests, add a CHANGELOG line under [Unreleased] ...
tools/check.sh && git add -A && git commit -m "<what and why>"
tools/release.sh
~~~

Answer `n` to "Release jetzt bauen?" to collect further features on
`develop` (optionally push `develop`); answer `j` to release at once. To
release the collected features later:

~~~bash
git switch develop && tools/release.sh
~~~

### Hotfix

A hotfix starts from `main`, so that it never ships unreleased features of
`develop`; the script refuses a hotfix branch that contains them.

~~~bash
git switch main && git pull --ff-only && git switch -c hotfix/<short-name>
# ... fix, test, CHANGELOG line under [Unreleased] ...
tools/check.sh && git add -A && git commit -m "Fix: <what>"
tools/release.sh -m "<release message>"
~~~

If `develop` already holds changes that conflict with the fix (often the
CHANGELOG), the script stops after tagging, leaves `main` and the tag local
and prints how to finish the merge into `develop` by hand.

### Without questions

~~~bash
tools/release.sh minor -m "<release message>" --yes
~~~

`--yes` answers every question with yes (release, push, install) and needs
`-m`. `tools/release.sh --help` lists all options.

`tools/same-code.sh A B [C ...]` answers JA or NEIN for any branches, tags
or commits: equal tree hashes mean identical files, even though the commit
hashes of merges differ.

### Which part?

| Part | The change ... |
|---|---|
| `patch` | corrects wrong behaviour; only tests, scripts or documentation |
| `minor` | adds something usable; everything that worked before still works |
| `major` | makes something that worked before stop working or behave differently |

The effect decides, not the place of the change; several rows: the highest.

### Patches from outside

Patches delivered by Claude come as archive `cyberghost-gui-<kind>-<name>.tar.gz`
with the patches and `patch.info` (branch, base and result hashes, part,
release message), never with a version number. Apply one on its branch after
checking the base hashes, then run `tools/release.sh` with the part and message
from `patch.info`. (A command `cyberghost-gui update` that does this is planned;
it does not exist yet.)

### Gates before every push

`tools/check.sh` runs all gates, including `shell` (shellcheck over every
shell script; `sudo apt install shellcheck` once). It activates the
development venv `.venv` by itself, so no `source .venv/bin/activate` is
needed before it, before `git push` (pre-push hook) or before
`tools/release.sh`.

## Coding rules

1. English for code, comments, docstrings, commit texts and documentation; the
   user interface is German.
2. External programs are started with argument lists, never through a shell.
3. Passwords never appear on a command line or in a log.
4. Nothing the user created is deleted without a request. Only what an earlier
   `install.sh` provably created (the old venv) is removed by `install.sh`.
5. User guide and developer guide are updated with every change.
6. The repository holds no personal names, hosts, addresses or vendor files.

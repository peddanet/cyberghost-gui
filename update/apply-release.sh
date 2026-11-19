#!/usr/bin/env bash
# apply-release.sh - integrate a delivered patch archive and install it.
#
#   ~/Downloads/cyberghost-gui-X.Y.Z-patch.tar.gz   contains *.patch
#
# Steps: rebuild the release branch from develop, git am, gates (pre-push hook),
# pull request for the CI run, fast-forward of develop and main, annotated tag,
# installation with live switch. History stays linear; a failed run can simply
# be repeated. Run as a normal user: git, gh and the venv belong to the user.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
ARCHIVE="${1:-$(ls -t "$HOME"/Downloads/cyberghost-gui-*-patch.tar.gz 2>/dev/null \
                | head -n 1 || true)}"
[ -f "$ARCHIVE" ] || { echo "no archive cyberghost-gui-X.Y.Z-patch.tar.gz found" >&2; exit 1; }
VERSION="$(basename "$ARCHIVE" | sed -n 's/^cyberghost-gui-\(.*\)-patch\.tar\.gz$/\1/p')"
[ -n "$VERSION" ] || { echo "unexpected archive name: $ARCHIVE" >&2; exit 1; }
BRANCH="release/$VERSION"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

step() { printf '\n=== %s\n' "$*"; }

step "check clean tree and archive"
[ -z "$(git status --porcelain)" ] || { echo "working tree is not clean" >&2; exit 1; }
tar -xzf "$ARCHIVE" -C "$WORK"
mapfile -t PATCHES < <(find "$WORK" -name '*.patch' | sort)
(( ${#PATCHES[@]} )) || { echo "archive holds no patch" >&2; exit 1; }
grep -qh "^+__version__ = \"$VERSION\"" "${PATCHES[@]}" \
    || { echo "patch does not set version $VERSION" >&2; exit 1; }

step "activate the project venv"
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --quiet -r requirements-dev.txt

step "apply on $BRANCH"
git fetch --prune origin
git switch develop && git merge --ff-only origin/develop
git switch -C "$BRANCH" develop
git am --3way "${PATCHES[@]}"
pip install --quiet -r requirements-dev.txt

step "push (pre-push hook runs all gates)"
git push --force-with-lease -u origin "$BRANCH"

step "pull request and CI"
gh pr view "$BRANCH" >/dev/null 2>&1 || gh pr create --base develop --fill --head "$BRANCH"
for _ in {1..24}; do        # the checks need a moment to appear
    code=0; gh pr checks "$BRANCH" >/dev/null 2>&1 || code=$?
    (( code == 0 || code == 8 )) && break
    sleep 5
done
gh pr checks "$BRANCH" --watch --interval 15

step "fast-forward develop and main, tag v$VERSION"
git switch develop && git merge --ff-only "$BRANCH" && git push origin develop
git switch main && git merge --ff-only origin/main && git merge --ff-only develop
git push origin main
git tag -a "v$VERSION" -m "cyberghost-gui $VERSION"
git push origin "v$VERSION"
git push origin --delete "$BRANCH"
git switch develop && git branch -d "$BRANCH"

step "install and switch the running application"
./install.sh --no-apt
DEST="${CGHOST_GUI_HOME:-$HOME/scripts/cyberghost-gui}"
install -d -m 700 "$DEST/releases"
mv -f "$ARCHIVE" "$DEST/releases/"
echo "applied: $VERSION"

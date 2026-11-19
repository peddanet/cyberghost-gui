#!/usr/bin/env bash
# first-publish.sh - create the local repository from the delivered patch, run
# all gates, create a PRIVATE GitHub repository, push and install.
#
# Usage: bash first-publish.sh     (next to 0001-*.patch; normal user)
# Nothing is pushed unless a local deny list exists and every gate is green.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${CGHOST_GUI_REPO:-$HOME/Projects/cyberghost-gui}"
step() { printf '\n=== %s\n' "$*"; }

gh auth status >/dev/null || { echo "gh is not logged in: gh auth login" >&2; exit 1; }
LISTS=("${CGHOST_GUI_HOME:-$HOME/scripts/cyberghost-gui}/privacy/denylist.txt"
       "$HOME/.config/mediatools/privacy/denylist.txt"
       "$HOME/.local/share/filetag/privacy/denylist.txt")
FOUND=0
for list in "${LISTS[@]}"; do
    [ -s "$list" ] && FOUND=1
done
if (( ! FOUND )); then
    printf 'no deny list found; copy yours to one of:\n' >&2
    printf '  %s\n' "${LISTS[@]}" >&2
    exit 1
fi
if [ -e "$TARGET" ]; then
    if git -C "$TARGET" remote get-url origin >/dev/null 2>&1; then
        echo "already published: $TARGET" >&2
        exit 1
    fi
    mv "$TARGET" "$TARGET.geloescht-$(date +%s)"     # leftover of an interrupted run
fi

step "packages for the gates (sudo)"
sudo apt-get install -y git python3-venv python3-gi gir1.2-gtk-4.0 xvfb

step "create repository in $TARGET"
git init -q -b main "$TARGET"
cd "$TARGET"
git am "$HERE"/0001-*.patch
git branch develop
git config core.hooksPath .githooks

step "virtual environment (source .venv/bin/activate)"
python3 -m venv --system-site-packages .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --quiet -r requirements-dev.txt

step "privacy gate must have a deny list"
python tools/privacy_scan.py --require

step "all quality gates"
tools/check.sh

step "create the private GitHub repository and push"
gh repo create cyberghost-gui --private --source . --remote origin \
    --description "Unofficial GTK front end for switching CyberGhost OpenVPN targets"
git push -u origin main develop
VERSION="$(python -c 'import cghostgui as c; print(c.__version__)')"
git tag -a "v$VERSION" -m "cyberghost-gui $VERSION"
git push origin "v$VERSION"
git switch -q develop
gh workflow run quality-gates --ref develop \
    || echo "CI not started; check that GitHub Actions are enabled for the repository"

step "install this release and switch the running application"
./install.sh

cat <<DONE

Done. The repository is private. After reviewing it on GitHub:
  gh repo edit --visibility public --accept-visibility-change-consequences
  tools/protect-branches.sh
DONE

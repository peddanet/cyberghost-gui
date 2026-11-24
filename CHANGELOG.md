# Changelog

All notable changes are listed here. New entries go under `## [Unreleased]`;
`tools/release.sh` turns that heading into the version heading of the release.

## [Unreleased]

## [0.6.0] - 2026-11-24

### Added

- `cyberghost-gui --version` and the command `~/.local/bin/cyberghost-gui`.
- `tools/release.sh` (git-flow with pull requests and required checks, GitHub
  variant of the dev-conventions) and `tools/same-code.sh` with their tests.
- Quality gate `shell`: shellcheck over every shell script, also in CI.
- The privacy gate also checks the names and e-mail addresses stored in commits
  and annotated tags (author, committer, tagger).

### Changed

- Folders follow the XDG layout: settings, imported configuration and privacy
  lists in `~/.config/cyberghost-gui`, program and official program in
  `~/.local/share/cyberghost-gui`, server lists in `~/.cache/cyberghost-gui`.
  Files of `~/scripts/cyberghost-gui` are moved once, without overwriting; the
  NetworkManager profile is pointed at the moved configuration.
- `install.sh` installs only a release tag that is on origin
  (`./install.sh vX.Y.Z`), never the working tree, and checks the installed version.
- `tools/check.sh` activates `.venv` only for the check and names missing tools.
- `tools/protect-branches.sh` allows the merge commits of `tools/release.sh` and
  requires branches to be up to date with their base.
- `update/apply-release.sh` and `tools/first-publish.sh` are replaced by
  `tools/release.sh` and have been removed.

## [0.5.1] - 2026-11-23

- Stored passwords are never discarded automatically. An expired CyberGhost session is
  renewed with the stored account password; a refused password leads to a question
  whether to retry it or to enter a new one.
- Clearer login dialogs: account e-mail address and account password are named as such.
- `install.sh` sets up autostart after login (window hidden, icon only).
- `first-publish.sh`: final hint uses a `gh repo edit` option every version knows.

## [0.5.0] - 2026-11-19

First public version.

- Target selection by country, city, server and streaming service; UDP and TCP.
- Connection through NetworkManager; import of a manual device configuration.
- Passwords in the key ring, asked once; new request only after a rejection.
- Clear handling of `AUTH_FAILED`.
- Panel indicator with live details; closing the window keeps it running.
- IPv6 block while connected; warning for differing reported locations.
- Update with live switch of the running application.

# AGENTS.md

This file provides guidance to AI coding agents when working with code in this repository.

## What this is

Lutris install scripts (YAML) for games where the published scripts don't fit the copies I own. Currently one: `diablo-ii-lod-original-cds.yml`, which installs Diablo II and Lord of Destruction from ISO images of the original retail CDs and runs them through the D2DX Glide wrapper. [`README.md`](./README.md) explains how that script works.

## Commands

```bash
# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

# Test
python3 -m pytest
python3 -m pytest tests/test_diablo_ii.py -v   # single file

# Lint
ruff check .
ruff format --check .
```

`pytest.ini` sets `pythonpath = tests`, so shared helpers are imported as `from lutris import ...`. That `tests/lutris.py` is a small mirror of how Lutris 0.5.22 substitutes variables and names its commands, not the real Lutris package.

CI (`.github/workflows/`) runs the tests, ruff and markdownlint. The required checks on `main` are `pytest`, `ruff` and `markdownlint`.

## Structure

- `*.yml` at the repo root: one installer script each. The generic tests pick up any new one automatically.
- `tests/test_installers.py`: checks every installer: required fields, known Lutris commands, defined variables, `bash -n` on shell steps, and a checksum for every download.
- `tests/test_diablo_ii.py`: guards for the problems found getting the Diablo II script working.
- `tests/lutris.py`: the Lutris semantics mirror described above.

## Conventions

- **Never commit ISOs, game files, CD keys or credentials.** Installers ask the user for their own discs at install time.
- Every `http(s)` download needs a `<id>_sha256` variable and a step that runs `$CACHE/checkhash.sh <id> $<id>_sha256`. The tests enforce this.
- Lutris substitutes `$VARIABLES` before the shell runs, so a shell variable must not share a name with a Lutris variable. The tests check this too, and run `bash -n` on every shell step after substitution.
- Wine hands the drive letters D: to J: to any CD it detects, and Proton resets S: and T: on every launch, so fake CD-ROM drives use other letters. `tests/test_diablo_ii.py` enforces it.
- D2DX comes from the `jackrayner/d2dx` fork's releases, pinned by tag URL and SHA-256. Release assets are never replaced, so a new release means a new URL and checksum. CI can't run the game, so test a new D2DX in the game before bumping the pin.
- Commit messages use Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`).
- After editing any `.md` file, run markdownlint with `.markdownlint.jsonc` (`npx markdownlint-cli2 "**/*.md"`) if Node is available; otherwise check the `markdownlint` job in CI.

# lutris-installers

Lutris install scripts for games where the published scripts don't fit the copies I own.

## Scripts

| Script | Game | What it's for |
|---|---|---|
| [`diablo-ii-original-cds`](./diablo-ii-original-cds/) | Diablo II + Lord of Destruction | The original 4 CD retail release, installed from ISO images, patched to 1.13c or 1.14d and run through D2DX |

## Installing a script

From the repository root:

```bash
lutris -i <script folder>/installer.yml
```

Each folder's README says what it asks for and how it works.

## Adding a script

1. Create `<name>/installer.yml` and `<name>/README.md`, and add a row to the table above.
2. The generic tests pick up `<name>/installer.yml` on their own. Add `tests/test_<name>.py` for guards specific to that script.
3. Every download needs a `<id>_sha256` variable and a step that checks it.

## Tests

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python3 -m pytest
```

They run offline without Lutris, and also in GitHub Actions on every push and pull request.

- **Every installer** (`tests/test_installers.py`): required fields, known Lutris commands, every `$variable` defined, shell steps that parse with `bash -n` after substitution, and a SHA-256 check for every download. They also catch shell variables that would be silently replaced by a Lutris variable of the same name.
- **The layout** (`tests/test_layout.py`): every script has its own folder, a fixed `installer.yml`, a README, and a link from this page.
- **The workflows** (`tests/test_workflows.py`): top-level permissions, pinned actions, and no `${{ }}` expressions inside `run` steps.
- **Script-specific guards** live in each script folder's README.

`tests/lutris.py` mirrors the parts of Lutris 0.5.22's installer behaviour the tests rely on.

## License

[MIT](./LICENSE)

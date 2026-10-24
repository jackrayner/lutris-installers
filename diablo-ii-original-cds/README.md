# Diablo II + Lord of Destruction (original 4 CD retail)

[`installer.yml`](./installer.yml) installs Diablo II and Lord of Destruction from ISO images of the original 2000/2001 retail discs (Install, Play Disc, Cinematics, Expansion), then applies the 1.13c or 1.14d patch. The [published Lutris scripts](https://lutris.net/games/diablo-ii-lord-of-destruction/) expect the later Battle Chest discs' `installer tome.mpq` layout, or only install the expansion.

```bash
lutris -i diablo-ii-original-cds/installer.yml
```

Run that from the repository root. Lutris asks for the four ISOs. In each installer, keep the default install folder, choose a Full installation, and exit when it finishes.

Requires `7z` and `sha256sum` on the host.

## How it works

- **No mounting:** the Windows (ISO 9660) side of each hybrid disc is extracted with `7z`.
- **Fake CD drives:** the installers check for a CD-ROM with the right volume label, so each disc gets its own Wine drive: R: Install, P: Play Disc, Q: Cinematics, U: Expansion. Each has a `.windows-label` file and a `cdrom` entry under `Wine\Drives`, so no disc swaps are needed.
- **Drive letters:** D: onwards are avoided because Wine assigns them to any CDs it detects, such as ISOs mounted on the host. S: and T: are avoided because Proton resets them on every launch.
- **Data files:** the music, video and expansion MPQs are copied into the game folder, so the patched game (1.12+) runs without a disc.
- **D2DX:** the game runs as `Game.exe -3dfx` through [D2DX](https://github.com/jackrayner/d2dx) (checksum-verified and pinned to a release; see below), a build of my fork of [bolrog/d2dx](https://github.com/bolrog/d2dx), not dgVoodoo2. The release's `SOURCE.txt` links the matching GPLv3 source. The original renderer keeps one CPU core at 100% even on the menus. With D2DX it measured about 15% in play here, and D2DX also scales cleanly and supports widescreen. `noclipcursor` is set so the mouse can leave the game window. The `nocompatmodefix` opt-out is set because D2DX's compatibility-mode check always fires under Wine: it compares `RtlGetVersion` with `NetServerGetInfo`, and Wine answers the latter from `GetVersionEx`.

## Tweaks

`d2dx.cfg` in the game folder takes [D2DX's options](https://github.com/jackrayner/d2dx/blob/main/d2dx-defaults.cfg). The two most useful:

- `size=[w,h]` under `[game]`: pick exactly half (or a third) of your screen resolution for crisp integer scaling, e.g. `size=[1128,752]` on a 2256×1504 screen.
- `nomotionprediction=true` under `[optouts]`: keep the game's native 25 fps instead of smooth motion at your refresh rate, which saves a little power.

## Keeping D2DX up to date

The script pins one release of the fork by URL and SHA-256 (`d2dx` and `d2dx_sha256` in `installer.yml`). A scheduled workflow, [`update-d2dx.yml`](../.github/workflows/update-d2dx.yml), runs daily and opens a pull request when `jackrayner/d2dx` publishes a newer release. It never merges anything.

Before it opens a pull request, [`scripts/update_d2dx.py`](../scripts/update_d2dx.py):

- picks the highest version among published, non-draft, non-prerelease releases (a numeric `X.Y.Z` tag with a `d2dx.zip` asset), and never downgrades
- downloads `d2dx.zip`, and requires its SHA-256 to match both GitHub's asset digest and the checksum in the release notes (at least one must exist)
- checks the size and that the zip has a top-level `glide3x.dll`, which the installer extracts

The workflow then runs the tests on the updated installer. CI can't run the game, so test each new release in a Diablo II install before merging. To check by hand, run `python3 scripts/update_d2dx.py --dry-run` from the repository root, add `--include-prereleases` to consider prereleases, or leave out `--dry-run` to edit `installer.yml` in place.

## Tests

- `tests/test_diablo_ii.py`: guards against the problems found getting this script working, such as disc drives on letters Wine or Proton take over, a copy loop that fails on its last item, and D2DX's Wine compatibility fix being dropped.
- `tests/test_update_d2dx.py`: release selection, the checksum cross-checks, the YAML rewrite and the never-downgrade and wrong-repo guards, all offline with fake releases.

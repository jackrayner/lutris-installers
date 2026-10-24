# lutris-installers

Lutris install scripts for games where the published scripts don't fit the copies I own.

## Diablo II + Lord of Destruction (original 4 CD retail)

[`diablo-ii-lod-original-cds.yml`](./diablo-ii-lod-original-cds.yml) installs Diablo II and Lord of Destruction from ISO images of the original 2000/2001 retail discs (Install, Play Disc, Cinematics, Expansion), then applies the 1.13c or 1.14d patch. The [published Lutris scripts](https://lutris.net/games/diablo-ii-lord-of-destruction/) expect the later Battle Chest discs' `installer tome.mpq` layout, or only install the expansion.

```bash
lutris -i diablo-ii-lod-original-cds.yml
```

Lutris asks for the four ISOs. In each installer, keep the default install folder, choose a Full installation, and exit when it finishes.

How it works:

- **No mounting:** the Windows (ISO 9660) side of each hybrid disc is extracted with `7z`.
- **Fake CD drives:** the installers check for a CD-ROM with the right volume label, so each disc gets its own Wine drive: R: Install, P: Play Disc, Q: Cinematics, U: Expansion. Each has a `.windows-label` file and a `cdrom` entry under `Wine\Drives`, so no disc swaps are needed.
- **Drive letters:** D: onwards are avoided because Wine assigns them to any CDs it detects, such as ISOs mounted on the host. S: and T: are avoided because Proton resets them on every launch.
- **Data files:** the music, video and expansion MPQs are copied into the game folder, so the patched game (1.12+) runs without a disc.
- **D2DX:** the game runs as `Game.exe -3dfx` through [D2DX](https://github.com/jackrayner/d2dx) 0.0.1 (checksum-verified), a build of my fork of [bolrog/d2dx](https://github.com/bolrog/d2dx), not dgVoodoo2. The release's `SOURCE.txt` links the matching GPLv3 source. The original renderer keeps one CPU core at 100% even on the menus. With D2DX it measured about 15% in play here, and D2DX also scales cleanly and supports widescreen. `noclipcursor` is set so the mouse can leave the game window. The `nocompatmodefix` opt-out is set because D2DX's compatibility-mode check always fires under Wine: it compares `RtlGetVersion` with `NetServerGetInfo`, and Wine answers the latter from `GetVersionEx`.

Requires `7z` and `sha256sum` on the host.

### Tweaks

`d2dx.cfg` in the game folder takes [D2DX's options](https://github.com/jackrayner/d2dx/blob/main/d2dx-defaults.cfg). The two most useful:

- `size=[w,h]` under `[game]`: pick exactly half (or a third) of your screen resolution for crisp integer scaling, e.g. `size=[1128,752]` on a 2256×1504 screen.
- `nomotionprediction=true` under `[optouts]`: keep the game's native 25 fps instead of smooth motion at your refresh rate, which saves a little power.

## Tests

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python3 -m pytest
```

They run offline without Lutris, and also in GitHub Actions on every push and pull request.

- **Every `*.yml` installer** (`tests/test_installers.py`): required fields, known Lutris commands, every `$variable` defined, shell steps that parse with `bash -n` after substitution, and a SHA-256 check for every download. They also catch shell variables that would be silently replaced by a Lutris variable of the same name.
- **The Diablo II script** (`tests/test_diablo_ii.py`): guards against the problems found getting it working, such as disc drives on letters Wine or Proton take over, a copy loop that fails on its last item, and D2DX's Wine compatibility fix being dropped.

`tests/lutris.py` mirrors the parts of Lutris 0.5.22's installer behaviour the tests rely on.

## License

[MIT](./LICENSE)

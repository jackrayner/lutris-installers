# The Settlers IV: Gold Edition (GOG)

[`installer.yml`](./installer.yml) installs The Settlers IV: Gold Edition from the GOG offline installer, then applies the community widescreen fix for a resolution you choose and a music fix. It is based on Armageddon91's "GOG + Fix" [Lutris script](https://lutris.net/games/the-settlers-iv-gold-edition/), with the downloads pinned and checked, and the originals kept.

```bash
lutris -i settlers-iv-gold-gog/installer.yml
```

Run that from the repository root. If you are logged in to GOG in Lutris (Sources, GOG) and own the game, Lutris downloads the offline installer for you. Otherwise it asks for the `setup_*.exe` from your GOG library. Either way a resolution menu follows. Requires `7z` and `sha256sum` on the host.

## How it works

- **GOG download:** `gogid` is the game's GOG product ID, and "GOG" in the script's version makes Lutris use its GOG service, which replaces the first `N/A:` file with a download from your library and checks it against GOG's checksum file. If you aren't logged in or don't own the game, Lutris falls back to asking for the file.
- **Silent install:** the GOG installer runs with `/SP- /silent /nogui`, so there are no screens to click through.
- **Widescreen fix:** the fix replaces the game's 1024x768 option with the resolution you pick, by swapping `GfxEngine.dll`. Choose your screen's resolution, or the closest one below it, and leave the in-game resolution alone. The menu offers the eight resolutions the fix ships: 1024x600 up to 1920x1200.
- **Music fix:** a replacement `SoundTracks.cfg` and the missing Trojan track. The Maya music then resumes after a Dark Tribe or combat theme, and Dark Tribe maps can play music.
- **Settings:** the fix's `GameSettings.cfg` is copied in with `WindowWidth` and `WindowHeight` set to your choice. The previous script only edited these in the cache, so the width could end up wrong.
- **Originals kept:** on the first run `GfxEngine.dll`, `SoundTracks.cfg` and `GameSettings.cfg` are saved next to the new files with an `.orig` suffix. A `.fixes-applied` marker stops a re-run from backing up already fixed files.
- **Pinned download:** the fix zip comes from a fixed commit of [Armageddon91/Lutris-Script](https://github.com/Armageddon91/Lutris-Script), not `master`, and its SHA-256 is checked before anything is installed. That repository has no licence, so nothing from it is stored here.

## Not verified

The fix and settings come from the published script. What the repository's tests run is the install step against a synthetic copy of the fix's folder layout. They can't run the game, so these are untested here:

- the automatic GOG download, which needs a GOG login
- the game starting at each resolution in Wine
- `Screenmode = 2` (the fix's value) giving the right mode. The previous script set `Screenmode = 4` instead.

## Tests

`tests/test_settlers_iv.py` checks that the fix is pinned to a commit, the GOG installer is silent, the menu matches the resolutions the fix ships, and the install step (run in a temporary folder) swaps the right files, sets the window size and never overwrites the first backups.

# The Settlers IV: Gold Edition (GOG)

[`installer.yml`](./installer.yml) installs The Settlers IV: Gold Edition from the GOG offline installer, then applies the community widescreen fix for a resolution you choose, a music fix, and [cnc-ddraw](https://github.com/FunkyFr3sh/cnc-ddraw) to stop the game using a whole CPU core. It is based on Armageddon91's "GOG + Fix" [Lutris script](https://lutris.net/games/the-settlers-iv-gold-edition/), with the downloads pinned and checked, and the originals kept.

```bash
lutris -i settlers-iv-gold-gog/installer.yml
```

Run that from the repository root. If you are logged in to GOG in Lutris (Sources, GOG) and own the game, Lutris downloads the offline installer for you. Otherwise it asks for the `setup_*.exe` from your GOG library. Either way a resolution menu follows. Requires `7z` and `sha256sum` on the host.

## How it works

- **GOG download:** `gogid` is the game's GOG product ID, and "GOG" in the script's version makes Lutris use its GOG service, which replaces the first `N/A:` file with a download from your library and checks it against GOG's checksum file. If you aren't logged in or don't own the game, Lutris falls back to asking for the file.
- **Silent install:** the GOG installer runs with `/SP- /silent /nogui`, so there are no screens to click through.
- **Widescreen fix:** the fix replaces the game's 1024x768 option with the resolution you pick. It works by changing two 16-bit numbers in `GfxEngine.dll` (the mode's width at byte 67214 and height at 67219), and the script makes that change itself on the fix's stock `GfxEngine.dll`, after checking those bytes read 1024 and 768. For the eight sizes the fix ships, the result is byte for byte the DLL it ships. The menu also offers sizes the fix doesn't ship: 2560x1440, 2560x1600 and 3840x2160 (4K); the 3:2 sizes 1800x1200, 2256x1504 and 2880x1920 (the last is a newer Framework 13 panel size); and three exact integer fractions of 3:2 panels: 1128x752 (1/2 of 2256x1504), 1440x960 (1/2 of 2880x1920) and 960x640 (1/3 of 2880x1920). An integer fraction is the one a panel scales up evenly, so it stays sharp. Choose your screen's resolution, or the closest one below it, and leave the in-game resolution alone.
- **Music fix:** a replacement `SoundTracks.cfg` and the missing Trojan track. The Maya music then resumes after a Dark Tribe or combat theme, and Dark Tribe maps can play music.
- **cnc-ddraw:** GOG's `ddraw.dll` is a small pass-through shim with a window hook and no frame limiter. The game's main loop spins one core at 100% waiting for each frame, which is the same problem Diablo II has. The script replaces the shim with cnc-ddraw v7.1.0.0 (MIT), whose default limiter holds the game to about 60 ticks a second. Its `ddraw.ini` is the stock one with `singlecpu=false`, because the default pins the game to CPU0. The release is pinned by URL and SHA-256. GitHub publishes no digest for it, so that hash is one I computed from the download. cnc-ddraw also takes over from the shim's window handling.
- **Settings:** the fix's `GameSettings.cfg` is copied in with `WindowWidth` and `WindowHeight` set to your choice, as a starting value. The game rewrites this file when it runs (after a play session the width read 1024 and the height 1200 for a 1920x1200 choice), so the resolution you get comes from the widescreen `GfxEngine.dll`, not from these two numbers.
- **Originals kept:** on the first run `GfxEngine.dll`, `ddraw.dll`, `SoundTracks.cfg` and `GameSettings.cfg` are saved next to the new files with an `.orig` suffix. A `.fixes-applied` marker stops a re-run from backing up already fixed files.
- **Pinned download:** the fix zip comes from a fixed commit of [Armageddon91/Lutris-Script](https://github.com/Armageddon91/Lutris-Script), not `master`, and its SHA-256 is checked before anything is installed. That repository has no licence, so nothing from it is stored here.

## Known limitation: a strip below the left panel

On screens taller than about 1024 pixels, a smeared strip shows down the left edge, directly below the interface panel. In a 3840x2160 screen recording the panel is a fixed picture about 208 pixels wide and 1025 tall, and the strip is about 160 pixels wide. Most of the sizes the game ships (640x480 up to 1280x1024) are no taller than the panel, so it covers the whole height. On a taller screen the area below the panel shows the game's landscape fill, stretched into streaks. This is the game's own behaviour, not something the script adds:

- It appears at the game's own 1600x1200, using the stock `GfxEngine.dll`, as reported from playing it.
- It was already there before cnc-ddraw was installed, with GOG's `ddraw.dll`, as reported from playing it.
- Putting the size in a different mode slot (1600x1200 instead of the fix's 1024x768 slot, with `Screenmode = 4`) makes no difference.
- Its height should be the screen height minus about 1024, so about 56 pixels at 1920x1080 and about 1100 at 3840x2160. That comes from the panel's measured size in the 4K recording. I haven't measured the strip at other sizes.

The game's own sizes up to 1280x1024 show none. By the same reasoning the custom sizes up to 1024 pixels high should show none either: 1024x600, 1280x720, 1280x800, 1366x768, 1440x900, 960x640, 1128x752 and 1440x960. None of those has been played, so that is a prediction. The menu marks the sizes taller than 1024 "panel gap". 1128x752 and 1440x960 are exact halves of 2256x1504 and 2880x1920, so they scale cleanly on those panels.

I haven't found a documented fix. A real one would mean changing the game's drawing code to clip the landscape at the panel's height, which this script doesn't attempt.

## Verified and not verified

Checked by installing and playing it with Lutris and Wine (GE-Proton) on a 2256x1504 screen:

- the automatic GOG download
- the install, and the game playing at 1920x1200, 1800x1200, 2256x1504 and 3840x2160 with the fix's `Screenmode = 2`. At 2256x1504 and at 3840x2160 the picture is sharp and fills the screen (the interface is small at 4K but usable), 1800x1200 is a bit soft because it doesn't scale evenly to the panel, and alt-tab and the mouse work
- CPU use, about 6 minutes at 1920x1200 for each `ddraw.dll`: with GOG's the whole process sat at 102% to 118% (median 111%) with its busiest thread at 87% on average, and with cnc-ddraw the median was 33% (average 39%, with short bursts to about 100%) and the busiest thread averaged 32%. GPU use fell from about 18% to 13%. At 2256x1504 with cnc-ddraw, a shorter run (about 90 seconds) showed 37% to 40% CPU and 12% to 13% GPU. At 3840x2160 a run of about 4 minutes had a median of 58% CPU (brief spikes to 102%) and 19% GPU (peak 39%), so 4K costs noticeably more than the smaller sizes. Memory stayed near 220 MB up to 2256x1504, and rose from 232 to 267 MB over the 4K run (flat for three minutes, then a step, so probably a map event, not a leak, but one short run can't prove it)

The repository's tests can't run the game. They run the install step against a synthetic copy of the fix's folder layout, and the install and extraction steps were also run against the real downloads: every size in the menu produces the expected DLL, and the ones the fix ships (plus 1800x1200, 2256x1504 and 3840x2160) match the fix's DLL or the DLL tested in the game byte for byte. Not tried in the game: every size except 1920x1200, 1800x1200, 2256x1504 and 3840x2160. The untested ones may hit limits in the game's engine or interface. 960x640 is narrower than the game's original 1024x768, so its interface may not fit.

Also not tried: longer sessions at 2256x1504, and the manual `setup_*.exe` fallback when you aren't logged in to GOG.

## Tests

`tests/test_settlers_iv.py` checks that the fix is pinned to a commit, the GOG installer is silent, cnc-ddraw is pinned to a release, the menu matches the sizes it can patch, and the install step (run in a temporary folder) patches only the four size bytes (and refuses an unexpected stock DLL), swaps the right files, installs cnc-ddraw with only its `[ddraw]` `singlecpu` setting changed, and never overwrites the first backups.

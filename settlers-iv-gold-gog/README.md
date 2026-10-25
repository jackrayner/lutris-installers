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

## Changing the resolution later

The size is set from an environment variable each time the game starts, so you can change it without reinstalling. In Lutris, right-click the game, then Configure, System options, Environment variables, and edit `S4_RESOLUTION`. It takes one of:

- `auto` (the default): the size of the primary display, read at every launch. The game always opens on the primary display, so this follows you when you dock or change the primary screen.
- `auto/2` or `auto/3`: an exact half or third of the primary display, which scales up evenly and stays sharp. If the display's size doesn't divide exactly (2256x1504 has no exact third), the size is left as it was.
- `WIDTHxHEIGHT`, for example `2256x1504`: any size from 1 to 65535 in each direction, not only the sizes in the menu.

The next launch applies it.

Where the game opens: with two displays side by side under GNOME and GE-Proton, the game opened on the primary display both times, whichever screen Lutris was on (laptop panel primary with Lutris on the 4K, then the 4K primary with Lutris on the laptop). Wine opens a fullscreen game on its primary monitor, and GNOME tells XWayland which one that is. That's why `auto` uses the primary display and not where the Lutris window is, which a script can't see on Wayland anyway.

How `auto` finds the size: on GNOME it asks the desktop's display service (`busctl`, Mutter's `DisplayConfig`) for the primary display's current mode, in physical pixels. Elsewhere, or if that fails, it uses the kernel's list of displays (`/sys/class/drm`), but only when exactly one display is connected and enabled, since the kernel doesn't know which is primary. Otherwise it leaves the size as it was. It was checked on GNOME with one and two displays; other desktops are untested, and with several displays on a desktop other than GNOME use a fixed size. Display scaling isn't taken into account: the tested displays were all at 100%.

How it works: the installer writes `set-resolution.sh` into the game folder and sets it as the game's pre-launch command, with "wait for completion" on, so Lutris finishes it before the game starts. The script works out the size, then patches the saved stock `GfxEngine.dll.orig` to it, using the same four bytes as the installer, and does nothing if the DLL already has that size. The installer runs the same script once, so there is one implementation.

The script never fails the launch. If the variable is missing or isn't one of the forms above, if `auto` can't tell the display's size, if a number is out of range, or if `GfxEngine.dll.orig` is missing or isn't the expected stock file, it prints a `[set-resolution]` line in Lutris's log and leaves the DLL as it is. The strip under the left panel (above) still applies to any size taller than 1024.

Lutris's DLL overrides table can't do this, because it only chooses whether Wine loads a native or built-in DLL by name, not what is inside it. It is the way to switch cnc-ddraw off (`ddraw` set to `builtin`) for a comparison.

The tests run the script directly (valid and invalid sizes, a missing or odd original, running from any folder, changing size repeatedly and back to 1024x768) and check the `system` section the installer writes. For `auto` they replay real GNOME layouts recorded on a laptop with a 4K display (with each display's vendor, model and serial removed) and fake kernel display lists, in `tests/data/`. Editing `S4_RESOLUTION` in the real Lutris interface has been tried with a fixed size: Lutris ran the script before the launch and the DLL changed. `auto` has also been launched from Lutris: after switching from a fixed 2256x1504 to `auto` with the 4K display primary, the game's own trace shows it playing at 3840x2160.

## Known limitation: a strip below the left panel

On screens taller than about 1024 pixels, a smeared strip shows down the left edge, directly below the interface panel. In a 3840x2160 screen recording the panel is a fixed picture about 208 pixels wide and 1025 tall, and the strip is about 160 pixels wide. Most of the sizes the game ships (640x480 up to 1280x1024) are no taller than the panel, so it covers the whole height. On a taller screen the area below the panel shows the game's landscape fill, stretched into streaks. This is the game's own behaviour, not something the script adds:

- It appears at the game's own 1600x1200, using the stock `GfxEngine.dll`, as reported from playing it.
- It was already there before cnc-ddraw was installed, with GOG's `ddraw.dll`, as reported from playing it.
- Putting the size in a different mode slot (1600x1200 instead of the fix's 1024x768 slot, with `Screenmode = 4`) makes no difference.
- Its height should be the screen height minus about 1024, so about 56 pixels at 1920x1080 and about 1100 at 3840x2160. That comes from the panel's measured size in the 4K recording. I haven't measured the strip at other sizes.

The game's own sizes up to 1280x1024 show none. By the same reasoning the custom sizes up to 1024 pixels high should show none either: 1024x600, 1280x720, 1280x800, 1366x768, 1440x900, 960x640, 1128x752 and 1440x960. None of those has been played, so that is a prediction. The menu marks the sizes taller than 1024 "panel gap". 1128x752 and 1440x960 are exact halves of 2256x1504 and 2880x1920, so they scale cleanly on those panels.

I haven't found a documented fix. A real one would mean changing the game's drawing code to clip the landscape at the panel's height, which this script doesn't attempt.

## Known limitation: unplugging the display the game is on

Unplugging the display the game is running on ends the game, as soon as it next becomes active (for example when you alt-tab back to it). It's a bug in Proton's Wine, seen with GE-Proton 11-11 on GNOME (XWayland), not something the script or cnc-ddraw causes. Relaunch afterwards; with `auto` the game opens at the new primary display's size.

What happens, from repeated tests with a 4K display unplugged mid-game:

1. At the unplug, Wine's desktop process (`explorer.exe /desktop`) disappears. All of its X11 connections close at that moment, and an X error is printed: `BadRROutput` on `RRGetOutputInfo`, a query about a display output, which fits it asking about the display that has just gone.
2. The game keeps running, but its windows depend on the desktop process's window. When the game is activated again it asks X11 to show that window (`X_MapWindow`), gets `BadWindow` and exits. Its own trace (`Log/TraceNNN.txt`) stops without "Closing trace file", the sign of a crash, not a quit.

These cnc-ddraw settings made no difference, so the script doesn't set them: `noactivateapp=true` (the game survived alt-tabbing away, then crashed coming back) and borderless window mode (`windowed=true`, `fullscreen=true`). Alt-tabbing without unplugging anything works normally. Untried: Wine's native Wayland driver (`PROTON_ENABLE_WAYLAND=1`), which doesn't use X11 and so shouldn't hit this, and other Proton versions.

## Verified and not verified

Checked by installing and playing it with Lutris and Wine (GE-Proton) on a 2256x1504 screen:

- the automatic GOG download
- the install, and the game playing at 1920x1200, 1800x1200, 2256x1504 and 3840x2160 with the fix's `Screenmode = 2`. At 2256x1504 and at 3840x2160 the picture is sharp and fills the screen (the interface is small at 4K but usable), 1800x1200 is a bit soft because it doesn't scale evenly to the panel, and alt-tab and the mouse work
- CPU use, about 6 minutes at 1920x1200 for each `ddraw.dll`: with GOG's the whole process sat at 102% to 118% (median 111%) with its busiest thread at 87% on average, and with cnc-ddraw the median was 33% (average 39%, with short bursts to about 100%) and the busiest thread averaged 32%. GPU use fell from about 18% to 13%. At 2256x1504 with cnc-ddraw, a shorter run (about 90 seconds) showed 37% to 40% CPU and 12% to 13% GPU. At 3840x2160 a run of about 4 minutes had a median of 58% CPU (brief spikes to 102%) and 19% GPU (peak 39%), so 4K costs noticeably more than the smaller sizes. Memory stayed near 220 MB up to 2256x1504, and rose from 232 to 267 MB over the 4K run (flat for three minutes, then a step, so probably a map event, not a leak, but one short run can't prove it)

The repository's tests can't run the game. They run the install step against a synthetic copy of the fix's folder layout, and the install and extraction steps were also run against the real downloads: every size in the menu produces the expected DLL, and the ones the fix ships (plus 1800x1200, 2256x1504 and 3840x2160) match the fix's DLL or the DLL tested in the game byte for byte. Not tried in the game: every size except 1920x1200, 1800x1200, 2256x1504 and 3840x2160. The untested ones may hit limits in the game's engine or interface. 960x640 is narrower than the game's original 1024x768, so its interface may not fit.

Also not tried: longer sessions at 2256x1504, and the manual `setup_*.exe` fallback when you aren't logged in to GOG.

## Tests

`tests/test_settlers_iv.py` checks that the fix is pinned to a commit, the GOG installer is silent, cnc-ddraw is pinned to a release, the menu matches the sizes it can patch, and the install step (run in a temporary folder) patches only the four size bytes (and refuses an unexpected stock DLL), swaps the right files, installs cnc-ddraw with only its `[ddraw]` `singlecpu` setting changed, and never overwrites the first backups.

"""Guards for the Settlers IV Gold (GOG) script."""

import json
import os
import re
import subprocess

import pytest
from lutris import REPO, file_urls, load, placeholder_values, steps, substitute

SCRIPT = REPO / "settlers-iv-gold-gog" / "installer.yml"
RESOLUTIONS = [
    "1024x600", "1280x720", "1280x800", "1366x768", "1440x900", "1680x1050", "1920x1080",
    "1920x1200", "2560x1440", "2560x1600", "960x640", "1128x752", "1440x960", "1800x1200",
    "2256x1504", "2880x1920", "3840x2160",
]  # fmt: skip
AUTO_OPTIONS = ["auto", "auto/2"]
DATA = REPO / "tests" / "data"
# The stock GfxEngine.dll keeps the 1024x768 mode as two 16-bit numbers at these offsets
WIDTH_AT, HEIGHT_AT = 67214, 67219


@pytest.fixture(scope="module")
def doc():
    return load(SCRIPT)


def _install_command(doc):
    return next(
        p["command"]
        for _, n, p in steps(doc)
        if n == "execute" and "S4.exe" in p.get("command", "")
    )


def test_fix_zip_pinned_to_a_commit_not_a_branch(doc):
    url = file_urls(doc)["fix"]
    assert re.search(r"/raw/[0-9a-f]{40}/", url), "pin the fix zip to a commit, branches can change"


def test_cnc_ddraw_pinned_to_a_release_tag(doc):
    url = file_urls(doc)["cncddraw"]
    assert re.search(r"/releases/download/v\d+(\.\d+)+/cnc-ddraw\.zip$", url), (
        "pin a release, not latest"
    )


def test_game_runs_s4_from_the_gog_folder(doc):
    game = doc["script"]["game"]
    assert game["exe"].endswith("/S4.exe")
    assert doc["script"]["variables"]["gamepath"] in game["exe"].replace(
        "$gamepath", doc["script"]["variables"]["gamepath"]
    )


def test_lutris_can_fetch_the_installer_from_gog(doc):
    # Lutris picks its GOG service when the version mentions GOG, and uses gogid to find the
    # game. It replaces the first N/A: file, so that must be the GOG installer.
    assert "gog" in doc["version"].lower()
    assert str(doc["gogid"]).isdigit()
    first = next(iter(file_urls(doc).values()))
    assert first.startswith("N/A")
    assert next(iter(file_urls(doc))) == "gog_setup"


def test_gog_installer_runs_silently(doc):
    run = next(p for _, n, p in steps(doc) if n == "task" and p.get("name") == "wineexec")
    assert run["executable"] == "gog_setup"
    assert "/silent" in run["args"].split()


def test_menu_offers_the_resolutions_it_can_patch(doc):
    menu = next(p for _, n, p in steps(doc) if n == "input_menu" and p.get("id") == "RES")
    assert [next(iter(o)) for o in menu["options"]] == AUTO_OPTIONS + RESOLUTIONS
    assert menu["preselect"] == "auto"


def _stock_dll():
    """A stand-in for the stock GfxEngine.dll: the 1024x768 mode sits at the real offsets."""
    stock = bytearray(b"stock" * 20000)
    stock[WIDTH_AT : WIDTH_AT + 2] = (1024).to_bytes(2, "little")
    stock[HEIGHT_AT : HEIGHT_AT + 2] = (768).to_bytes(2, "little")
    return bytes(stock)


def _size(dll_bytes):
    width = int.from_bytes(dll_bytes[WIDTH_AT : WIDTH_AT + 2], "little")
    height = int.from_bytes(dll_bytes[HEIGHT_AT : HEIGHT_AT + 2], "little")
    return width, height


@pytest.fixture
def game(doc, tmp_path):
    """A fake GOG install plus an extracted fix folder with the layout of the real zip."""
    root = tmp_path / "game" / doc["script"]["variables"]["gamepath"]
    for d in ("Exe", "Config", "Snd"):
        (root / d).mkdir(parents=True)
    (root / "S4.exe").write_text("exe")
    (root / "Exe/GfxEngine.dll").write_bytes(_stock_dll())
    (root / "Config/GameSettings.cfg").write_text("original settings")
    fix = tmp_path / "cache/s4fix/The Settler 4 Fix"
    (root / "Exe/ddraw.dll").write_text("gog ddraw")
    cnc = tmp_path / "cache/cncddraw"
    cnc.mkdir(parents=True)
    (cnc / "ddraw.dll").write_text("cnc ddraw")
    (cnc / "ddraw.ini").write_bytes(
        b"[ddraw]\r\nmaxfps=-1\r\nsinglecpu=true\r\n\r\n[other]\r\nsinglecpu=true\r\n"
    )
    (fix / "Music Fix").mkdir(parents=True)
    (fix / "Music Fix/SoundTracks.cfg").write_text("fixed tracks")
    (fix / "Music Fix/Trojans_settle_03.mp3").write_text("mp3")
    (fix / "GameSettings.cfg").write_text(
        "    WindowHeight = 786\n    WindowWidth = 1024\n    Screenmode = 2\n"
    )
    return root


def _values(doc, tmp_path, res=""):
    values = placeholder_values(doc)
    values.update(
        GAMEDIR=str(tmp_path / "game"),
        CACHE=str(tmp_path / "cache"),
        INPUT=res,
        gamepath=doc["script"]["variables"]["gamepath"],
    )
    return values


def _write_launch_script(doc, tmp_path):
    """Write set-resolution.sh the way the installer's write_file step does."""
    step = next(
        p
        for _, n, p in steps(doc)
        if n == "write_file" and p["file"].endswith("/set-resolution.sh")
    )
    path = tmp_path / "game" / "set-resolution.sh"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(substitute(step["content"], _values(doc, tmp_path)))
    path.chmod(0o755)
    return path


def _run_install(doc, tmp_path, res, env=None):
    _write_launch_script(doc, tmp_path)
    return subprocess.run(
        ["bash", "-c", substitute(_install_command(doc), _values(doc, tmp_path, res))],
        capture_output=True,
        text=True,
        env=env,
    )


def _run(doc, tmp_path, res):
    result = _run_install(doc, tmp_path, res)
    assert result.returncode == 0, result.stdout + result.stderr


def test_install_step_applies_fixes_and_sets_window_size(doc, game, tmp_path):
    _run(doc, tmp_path, "1280x800")
    assert _size((game / "Exe/GfxEngine.dll").read_bytes()) == (1280, 800)
    assert (game / "Config/SoundTracks.cfg").read_text() == "fixed tracks"
    assert (game / "Snd/Trojans_settle_03.mp3").exists()
    settings = (game / "Config/GameSettings.cfg").read_text()
    assert "WindowWidth = 1280" in settings
    assert "WindowHeight = 800" in settings
    assert "Screenmode = 2" in settings


def test_install_step_installs_cnc_ddraw_without_cpu_pinning(doc, game, tmp_path):
    _run(doc, tmp_path, "1920x1200")
    assert (game / "Exe/ddraw.dll").read_text() == "cnc ddraw"
    ini = (game / "Exe/ddraw.ini").read_bytes()
    # only the [ddraw] section's setting changes, and the file's line endings survive
    assert ini == b"[ddraw]\r\nmaxfps=-1\r\nsinglecpu=false\r\n\r\n[other]\r\nsinglecpu=true\r\n"


def test_install_step_keeps_originals_even_when_run_twice(doc, game, tmp_path):
    _run(doc, tmp_path, "1920x1080")
    _run(doc, tmp_path, "1280x720")
    assert (game / "Exe/GfxEngine.dll.orig").read_bytes() == _stock_dll()
    assert (game / "Config/GameSettings.cfg.orig").read_text() == "original settings"
    assert (game / "Exe/ddraw.dll.orig").read_text() == "gog ddraw"
    assert not (game / "Config/SoundTracks.cfg.orig").exists()
    assert _size((game / "Exe/GfxEngine.dll").read_bytes()) == (1280, 720)


def test_patch_changes_only_the_four_size_bytes(doc, game, tmp_path):
    _run(doc, tmp_path, "2256x1504")
    stock = _stock_dll()
    dll = (game / "Exe/GfxEngine.dll").read_bytes()
    assert len(dll) == len(stock)
    changed = [i for i in range(len(dll)) if dll[i] != stock[i]]
    assert changed == [WIDTH_AT, WIDTH_AT + 1, HEIGHT_AT, HEIGHT_AT + 1]
    assert _size(dll) == (2256, 1504)


def test_install_step_fails_loudly_on_an_unexpected_stock_dll(doc, game, tmp_path):
    odd = bytearray(_stock_dll())
    odd[WIDTH_AT] = 0x55
    (game / "Exe/GfxEngine.dll").write_bytes(odd)
    result = _run_install(doc, tmp_path, "1920x1200")
    assert result.returncode != 0
    assert "could not set the resolution" in result.stdout
    assert (game / "Exe/GfxEngine.dll").read_bytes() == bytes(odd)


def test_system_config_runs_set_resolution_before_launch(doc):
    system = doc["script"]["system"]
    assert system["env"] == {"S4_RESOLUTION": "$INPUT_RES"}
    assert system["prelaunch_command"] == '"$GAMEDIR/set-resolution.sh"'
    assert system["prelaunch_wait"] is True


def test_launch_script_is_valid_bash_with_install_time_values_substituted(doc, tmp_path):
    script = _write_launch_script(doc, tmp_path)
    assert subprocess.run(["bash", "-n", str(script)]).returncode == 0
    assert script.read_text().startswith("#!/bin/bash\n")
    assert "$gamepath" not in script.read_text()  # substituted at install time


def _launch(doc, tmp_path, size, cwd=None, args=(), env=None):
    script = _write_launch_script(doc, tmp_path)
    env = {k: v for k, v in (env or os.environ).items() if k != "S4_RESOLUTION"}
    if size is not None:
        env["S4_RESOLUTION"] = size
    return subprocess.run(
        [str(script), *args], capture_output=True, text=True, env=env, cwd=cwd or tmp_path
    )


@pytest.fixture
def saved_stock(game):
    """The state after install: the stock DLL saved as .orig, a patched one in place."""
    (game / "Exe/GfxEngine.dll.orig").write_bytes(_stock_dll())
    return game


@pytest.mark.parametrize("size", ["2256x1504", "01920x01080", "1x1", "65535x65535"])
def test_launch_script_patches_the_size_from_the_environment(doc, saved_stock, tmp_path, size):
    result = _launch(doc, tmp_path, size, cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    width, height = (int(x) for x in size.split("x"))
    assert _size((saved_stock / "Exe/GfxEngine.dll").read_bytes()) == (width, height)
    assert not (saved_stock / "Exe/GfxEngine.dll.new").exists()


@pytest.mark.parametrize(
    "size",
    [None, "", "abc", "1920", "1920x", "x1080", "0x0", "0x600", "800x0", "70000x100", "100x70000",
     "123456x100", "-5x10", " 1920x1080", "1920x1080 ", "1920x1080; touch pwned", "1920X1080"],
)  # fmt: skip
def test_launch_script_ignores_bad_sizes_and_never_fails_the_launch(
    doc, saved_stock, tmp_path, size
):
    before = (saved_stock / "Exe/GfxEngine.dll").read_bytes()
    result = _launch(doc, tmp_path, size)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "leaving the resolution as it is" in result.stdout
    assert (saved_stock / "Exe/GfxEngine.dll").read_bytes() == before
    assert not (tmp_path / "pwned").exists()


def test_launch_script_leaves_the_dll_alone_without_a_saved_original(doc, game, tmp_path):
    before = (game / "Exe/GfxEngine.dll").read_bytes()
    result = _launch(doc, tmp_path, "1920x1080")
    assert result.returncode == 0
    assert "not found" in result.stdout
    assert (game / "Exe/GfxEngine.dll").read_bytes() == before


def test_launch_script_refuses_an_unexpected_original(doc, game, tmp_path):
    odd = bytearray(_stock_dll())
    odd[HEIGHT_AT] = 0x55
    (game / "Exe/GfxEngine.dll.orig").write_bytes(odd)
    before = (game / "Exe/GfxEngine.dll").read_bytes()
    result = _launch(doc, tmp_path, "1920x1080")
    assert result.returncode == 0
    assert "not the expected stock file" in result.stdout
    assert (game / "Exe/GfxEngine.dll").read_bytes() == before


def test_launch_script_can_change_the_size_again_and_back(doc, saved_stock, tmp_path):
    dll = saved_stock / "Exe/GfxEngine.dll"
    for size in ("3840x2160", "1128x752", "3840x2160", "1024x768"):
        assert _launch(doc, tmp_path, size).returncode == 0
        assert _size(dll.read_bytes()) == tuple(int(x) for x in size.split("x"))
    assert dll.read_bytes() == _stock_dll()  # 1024x768 is the stock file again


def test_three_by_two_labels_are_really_three_by_two(doc):
    menu = next(p for _, n, p in steps(doc) if n == "input_menu" and p.get("id") == "RES")
    for option in menu["options"]:
        ((res, label),) = option.items()
        if res in AUTO_OPTIONS:
            continue
        w, h = map(int, res.split("x"))
        if "3:2" in label:
            assert w * 2 == h * 3, f"{res} is labelled 3:2"


def test_integer_fraction_labels_are_exact(doc):
    menu = next(p for _, n, p in steps(doc) if n == "input_menu" and p.get("id") == "RES")
    for option in menu["options"]:
        ((res, label),) = option.items()
        if res in AUTO_OPTIONS:
            continue
        match = re.search(r"1/(\d) of (\d+)x(\d+)", label)
        if match:
            k, panel_w, panel_h = map(int, match.groups())
            w, h = map(int, res.split("x"))
            assert (w * k, h * k) == (panel_w, panel_h), (
                f"{res} is not 1/{k} of {panel_w}x{panel_h}"
            )


@pytest.mark.parametrize("res", RESOLUTIONS)
def test_every_menu_size_is_patched_into_the_dll(doc, game, tmp_path, res):
    _run(doc, tmp_path, res)
    dll = (game / "Exe/GfxEngine.dll").read_bytes()
    w, h = map(int, res.split("x"))
    assert int.from_bytes(dll[WIDTH_AT : WIDTH_AT + 2], "little") == w
    assert int.from_bytes(dll[HEIGHT_AT : HEIGHT_AT + 2], "little") == h


# The left panel is a fixed bitmap about 1024 pixels tall; on taller screens a strip shows below it
PANEL_HEIGHT = 1024


def test_menu_marks_exactly_the_sizes_that_show_the_panel_gap(doc):
    menu = next(p for _, n, p in steps(doc) if n == "input_menu" and p.get("id") == "RES")
    for option in menu["options"]:
        ((res, label),) = option.items()
        if res in AUTO_OPTIONS:
            continue
        height = int(res.split("x")[1])
        assert ("panel gap" in label) == (height > PANEL_HEIGHT), f"{res}: {label}"


def _gnome(tmp_path, layout):
    """An environment whose busctl replays a recorded GNOME layout, or fails if None."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    stub = bin_dir / "busctl"
    if layout:
        stub.write_text(f"#!/bin/sh\ncat '{DATA / layout}'\n")
    else:
        stub.write_text("#!/bin/sh\nexit 1\n")
    stub.chmod(0o755)
    return {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"}


def _drm(tmp_path, *outputs):
    """A fake /sys/class/drm: (name, status, enabled, first mode) per output."""
    drm = tmp_path / "drm"
    drm.mkdir(exist_ok=True)
    for name, status, enabled, mode in outputs:
        out = drm / name
        out.mkdir()
        (out / "status").write_text(status + "\n")
        (out / "enabled").write_text(enabled + "\n")
        (out / "modes").write_text(f"{mode}\n1920x1080\n" if mode else "")
    return drm


@pytest.mark.parametrize(
    ("layout", "size", "expected"),
    [
        ("gnome-4k-primary.json", "auto", (3840, 2160)),
        ("gnome-4k-primary.json", "auto/2", (1920, 1080)),
        ("gnome-4k-primary.json", "auto/3", (1280, 720)),
        ("gnome-laptop-primary.json", "auto", (2256, 1504)),
        ("gnome-laptop-primary.json", "auto/2", (1128, 752)),
        ("gnome-laptop-only.json", "auto", (2256, 1504)),
    ],
)
def test_auto_uses_the_gnome_primary_display(doc, saved_stock, tmp_path, layout, size, expected):
    # the recorded layouts have two screens, and the game opens on whichever is primary
    result = _launch(doc, tmp_path, size, env=_gnome(tmp_path, layout))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "GNOME primary display" in result.stdout
    assert _size((saved_stock / "Exe/GfxEngine.dll").read_bytes()) == expected


def test_auto_refuses_a_fraction_that_does_not_divide_exactly(doc, saved_stock, tmp_path):
    before = (saved_stock / "Exe/GfxEngine.dll").read_bytes()
    env = _gnome(tmp_path, "gnome-laptop-primary.json")
    result = _launch(doc, tmp_path, "auto/3", env=env)  # 1504 / 3 isn't whole
    assert result.returncode == 0
    assert "does not divide exactly" in result.stdout
    assert (saved_stock / "Exe/GfxEngine.dll").read_bytes() == before


def test_auto_falls_back_to_the_only_connected_display(doc, saved_stock, tmp_path):
    drm = _drm(
        tmp_path,
        ("card1-eDP-1", "connected", "enabled", "2256x1504"),
        ("card1-DP-1", "disconnected", "disabled", "3840x2160"),
        ("card1-Writeback-1", "unknown", "disabled", ""),
    )
    result = _launch(doc, tmp_path, "auto/2", args=[str(drm)], env=_gnome(tmp_path, None))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "only connected display, card1-eDP-1" in result.stdout
    assert _size((saved_stock / "Exe/GfxEngine.dll").read_bytes()) == (1128, 752)


@pytest.mark.parametrize(
    "outputs",
    [
        [
            ("card1-eDP-1", "connected", "enabled", "2256x1504"),
            ("card1-DP-3", "connected", "enabled", "3840x2160"),
        ],
        [("card1-eDP-1", "connected", "disabled", "2256x1504")],
        [],
    ],
    ids=["two displays", "only a disabled one", "none"],
)  # fmt: skip
def test_auto_without_gnome_does_not_guess(doc, saved_stock, tmp_path, outputs):
    before = (saved_stock / "Exe/GfxEngine.dll").read_bytes()
    drm = _drm(tmp_path, *outputs)
    result = _launch(doc, tmp_path, "auto", args=[str(drm)], env=_gnome(tmp_path, None))
    assert result.returncode == 0
    assert "could not tell the primary display's size" in result.stdout
    assert (saved_stock / "Exe/GfxEngine.dll").read_bytes() == before


def test_auto_ignores_a_gnome_layout_without_a_primary(doc, saved_stock, tmp_path):
    layout = json.loads((DATA / "gnome-4k-primary.json").read_text())
    for logical in layout["data"][2]:
        logical[4] = False
    (tmp_path / "no-primary.json").write_text(json.dumps(layout))
    env = _gnome(tmp_path, None)
    (tmp_path / "bin/busctl").write_text(f"#!/bin/sh\ncat '{tmp_path / 'no-primary.json'}'\n")
    drm = _drm(tmp_path, ("card1-eDP-1", "connected", "enabled", "2256x1504"))
    result = _launch(doc, tmp_path, "auto", args=[str(drm)], env=env)
    assert "only connected display" in result.stdout
    assert _size((saved_stock / "Exe/GfxEngine.dll").read_bytes()) == (2256, 1504)


@pytest.mark.parametrize("size", ["auto/0", "auto/10", "auto/", "Auto", "auto/2x"])
def test_malformed_auto_values_are_refused(doc, saved_stock, tmp_path, size):
    before = (saved_stock / "Exe/GfxEngine.dll").read_bytes()
    result = _launch(doc, tmp_path, size, env=_gnome(tmp_path, "gnome-4k-primary.json"))
    assert result.returncode == 0
    assert "leaving the resolution as it is" in result.stdout
    assert (saved_stock / "Exe/GfxEngine.dll").read_bytes() == before


def test_install_step_with_auto(doc, game, tmp_path):
    env = _gnome(tmp_path, "gnome-laptop-primary.json")
    result = _run_install(doc, tmp_path, "auto", env=env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert _size((game / "Exe/GfxEngine.dll").read_bytes()) == (2256, 1504)
    # the fix's settings file keeps its own size instead of the literal "auto"
    settings = (game / "Config/GameSettings.cfg").read_text()
    assert "WindowWidth = 1024" in settings
    assert "auto" not in settings

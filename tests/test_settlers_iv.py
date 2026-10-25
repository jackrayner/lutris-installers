"""Guards for the Settlers IV Gold (GOG) script."""

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
    assert [next(iter(o)) for o in menu["options"]] == RESOLUTIONS
    assert menu["preselect"] in RESOLUTIONS


@pytest.fixture
def game(doc, tmp_path):
    """A fake GOG install plus an extracted fix folder with the layout of the real zip."""
    root = tmp_path / "game" / doc["script"]["variables"]["gamepath"]
    for d in ("Exe", "Config", "Snd"):
        (root / d).mkdir(parents=True)
    (root / "S4.exe").write_text("exe")
    (root / "Exe/GfxEngine.dll").write_text("original dll")
    (root / "Config/GameSettings.cfg").write_text("original settings")
    fix = tmp_path / "cache/s4fix/The Settler 4 Fix"
    stock = bytearray(b"stock" * 20000)
    stock[WIDTH_AT : WIDTH_AT + 2] = (1024).to_bytes(2, "little")
    stock[HEIGHT_AT : HEIGHT_AT + 2] = (768).to_bytes(2, "little")
    (fix / "Widescreen Fix/Standard").mkdir(parents=True)
    (fix / "Widescreen Fix/Standard/GfxEngine.dll").write_bytes(stock)
    (root / "Exe/ddraw.dll").write_text("gog ddraw")
    cnc = tmp_path / "cache/cncddraw"
    cnc.mkdir()
    (cnc / "ddraw.dll").write_text("cnc ddraw")
    (cnc / "ddraw.ini").write_bytes(
        b"[ddraw]\r\nmaxfps=-1\r\nsinglecpu=true\r\n\r\n[other]\r\nsinglecpu=true\r\n"
    )
    (fix / "Music Fix").mkdir()
    (fix / "Music Fix/SoundTracks.cfg").write_text("fixed tracks")
    (fix / "Music Fix/Trojans_settle_03.mp3").write_text("mp3")
    (fix / "GameSettings.cfg").write_text(
        "    WindowHeight = 786\n    WindowWidth = 1024\n    Screenmode = 2\n"
    )
    return root


def _run(doc, tmp_path, res):
    values = placeholder_values(doc)
    values.update(
        GAMEDIR=str(tmp_path / "game"),
        CACHE=str(tmp_path / "cache"),
        INPUT=res,
        gamepath=doc["script"]["variables"]["gamepath"],
    )
    result = subprocess.run(
        ["bash", "-c", substitute(_install_command(doc), values)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_install_step_applies_fixes_and_sets_window_size(doc, game, tmp_path):
    _run(doc, tmp_path, "1280x800")
    dll = (game / "Exe/GfxEngine.dll").read_bytes()
    assert int.from_bytes(dll[WIDTH_AT : WIDTH_AT + 2], "little") == 1280
    assert int.from_bytes(dll[HEIGHT_AT : HEIGHT_AT + 2], "little") == 800
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
    assert (game / "Exe/GfxEngine.dll.orig").read_text() == "original dll"
    assert (game / "Config/GameSettings.cfg.orig").read_text() == "original settings"
    assert (game / "Exe/ddraw.dll.orig").read_text() == "gog ddraw"
    assert not (game / "Config/SoundTracks.cfg.orig").exists()
    dll = (game / "Exe/GfxEngine.dll").read_bytes()
    assert int.from_bytes(dll[WIDTH_AT : WIDTH_AT + 2], "little") == 1280
    assert int.from_bytes(dll[HEIGHT_AT : HEIGHT_AT + 2], "little") == 720


def test_patch_changes_only_the_four_size_bytes(doc, game, tmp_path):
    stock = (
        tmp_path / "cache/s4fix/The Settler 4 Fix/Widescreen Fix/Standard/GfxEngine.dll"
    ).read_bytes()
    _run(doc, tmp_path, "2256x1504")
    dll = (game / "Exe/GfxEngine.dll").read_bytes()
    assert len(dll) == len(stock)
    changed = [i for i in range(len(dll)) if dll[i] != stock[i]]
    assert changed == [WIDTH_AT, WIDTH_AT + 1, HEIGHT_AT, HEIGHT_AT + 1]
    assert dll[WIDTH_AT : WIDTH_AT + 2] == (2256).to_bytes(2, "little")
    assert dll[HEIGHT_AT : HEIGHT_AT + 2] == (1504).to_bytes(2, "little")


def test_install_step_refuses_an_unexpected_stock_dll(doc, game, tmp_path):
    path = tmp_path / "cache/s4fix/The Settler 4 Fix/Widescreen Fix/Standard/GfxEngine.dll"
    data = bytearray(path.read_bytes())
    data[WIDTH_AT] = 0x55
    path.write_bytes(data)
    values = placeholder_values(doc)
    values.update(
        GAMEDIR=str(tmp_path / "game"),
        CACHE=str(tmp_path / "cache"),
        INPUT="1920x1200",
        gamepath=doc["script"]["variables"]["gamepath"],
    )
    result = subprocess.run(
        ["bash", "-c", substitute(_install_command(doc), values)], capture_output=True, text=True
    )
    assert result.returncode != 0
    assert (game / "Exe/GfxEngine.dll").read_text() == "original dll"


def test_three_by_two_labels_are_really_three_by_two(doc):
    menu = next(p for _, n, p in steps(doc) if n == "input_menu" and p.get("id") == "RES")
    for option in menu["options"]:
        ((res, label),) = option.items()
        w, h = map(int, res.split("x"))
        if "3:2" in label:
            assert w * 2 == h * 3, f"{res} is labelled 3:2"


def test_integer_fraction_labels_are_exact(doc):
    menu = next(p for _, n, p in steps(doc) if n == "input_menu" and p.get("id") == "RES")
    for option in menu["options"]:
        ((res, label),) = option.items()
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
        height = int(res.split("x")[1])
        assert ("panel gap" in label) == (height > PANEL_HEIGHT), f"{res}: {label}"

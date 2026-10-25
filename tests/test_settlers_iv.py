"""Guards for the Settlers IV Gold (GOG) script."""

import re
import subprocess

import pytest
from lutris import REPO, file_urls, load, placeholder_values, steps, substitute

SCRIPT = REPO / "settlers-iv-gold-gog" / "installer.yml"
RESOLUTIONS = [
    "1024x600", "1280x720", "1280x800", "1366x768",
    "1440x900", "1680x1050", "1920x1080", "1920x1200",
]  # fmt: skip


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


def test_menu_offers_the_resolutions_the_fix_ships(doc):
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
    for res in RESOLUTIONS:
        (fix / "Widescreen Fix" / res).mkdir(parents=True)
        (fix / "Widescreen Fix" / res / "GfxEngine.dll").write_text(f"dll {res}")
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
    assert (game / "Exe/GfxEngine.dll").read_text() == "dll 1280x800"
    assert (game / "Config/SoundTracks.cfg").read_text() == "fixed tracks"
    assert (game / "Snd/Trojans_settle_03.mp3").exists()
    settings = (game / "Config/GameSettings.cfg").read_text()
    assert "WindowWidth = 1280" in settings
    assert "WindowHeight = 800" in settings
    assert "Screenmode = 2" in settings


def test_install_step_keeps_originals_even_when_run_twice(doc, game, tmp_path):
    _run(doc, tmp_path, "1920x1080")
    _run(doc, tmp_path, "1280x720")
    assert (game / "Exe/GfxEngine.dll.orig").read_text() == "original dll"
    assert (game / "Config/GameSettings.cfg.orig").read_text() == "original settings"
    assert not (game / "Config/SoundTracks.cfg.orig").exists()
    assert (game / "Exe/GfxEngine.dll").read_text() == "dll 1280x720"

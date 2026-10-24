"""Guards for problems hit while getting the Diablo II script working."""

import re

import pytest
from lutris import REPO, load, steps

SCRIPT = REPO / "diablo-ii-lod-original-cds.yml"

# Wine hands D: onwards to CD drives it detects (e.g. ISOs mounted on the host)
# and Proton resets S: (game library) and T: (Steam) on every launch
RESERVED_LETTERS = set("defghij") | {"s", "t"}


@pytest.fixture(scope="module")
def doc():
    return load(SCRIPT)


def _commands(doc):
    return [p["command"] for _, n, p in steps(doc) if n == "execute" and "command" in p]


def disc_drives(doc):
    """{letter: (cache folder, volume label)} from the drive-setup step."""
    drives = {}
    for command in _commands(doc):
        links = re.findall(r'ln -sfn "\$CACHE/([\w-]+)" ([a-z]):', command)
        labels = dict(re.findall(r'echo (\S+) > "\$CACHE/([\w-]+)/\.windows-label"', command))
        labels = {folder: label for label, folder in labels.items()}
        for folder, letter in links:
            drives[letter] = (folder, labels.get(folder))
    return drives


def test_four_disc_drives_with_labels(doc):
    drives = disc_drives(doc)
    labels = sorted(label for _, label in drives.values())
    assert labels == ["CINEMATICS", "Expansion", "INSTALL", "PLAYDISC"]


def test_disc_drives_avoid_reserved_letters(doc):
    clash = set(disc_drives(doc)) & RESERVED_LETTERS
    assert not clash, f"drive letters {sorted(clash)} are taken by Wine or Proton"


def test_disc_drives_registered_as_cdrom(doc):
    cdroms = {
        p["key"].rstrip(":")
        for _, n, p in steps(doc)
        if n == "task" and p.get("name") == "set_regedit" and p.get("value") == "cdrom"
    }
    assert set(disc_drives(doc)) == cdroms


def test_wine_restarted_after_drive_setup(doc):
    names = [(n, p.get("name")) for _, n, p in steps(doc)]
    last_regedit = max(i for i, x in enumerate(names) if x == ("task", "set_regedit"))
    first_installer = min(i for i, x in enumerate(names) if x == ("task", "wineexec"))
    assert ("task", "winekill") in names[last_regedit:first_installer]


def test_installers_run_from_disc_drives(doc):
    drives = disc_drives(doc)
    runs = [p for _, n, p in steps(doc) if n == "task" and p.get("name") == "wineexec"]
    letters = [re.search(r"dosdevices/([a-z]):", p["executable"]).group(1) for p in runs]
    assert [drives[x][1] for x in letters] == ["INSTALL", "Expansion"]


def test_drive_links_removed_at_end(doc):
    cleanup = _commands(doc)[-1]
    for letter in disc_drives(doc):
        assert f'dosdevices/{letter}:"' in cleanup


def test_mpq_copy_loop_cannot_fail_on_last_item(doc):
    # A trailing `[ -n "$src" ] && cp ...` makes the loop exit 1 when the last
    # file isn't on any disc, which Lutris reports as "exited with code 256"
    loop = next(c for c in _commands(doc) if "for mpq in" in c)
    assert not re.search(r"\]\s*&&\s*cp\b[^;]*;\s*done", loop)


def test_runs_through_d2dx(doc):
    game = doc["script"]["game"]
    assert game["exe"].endswith("/Game.exe")
    assert "-3dfx" in game["args"].split()
    assert doc["script"]["wine"]["dgvoodoo2"] is False


def test_d2dx_config_handles_wine(doc):
    cfg = next(
        p["content"]
        for _, n, p in steps(doc)
        if n == "write_file" and p["file"].endswith("/d2dx.cfg")
    )
    assert "[optouts]" in cfg
    assert "nocompatmodefix=true" in cfg


def test_patch_menu_only_offers_d2dx_versions(doc):
    menu = next(p for _, n, p in steps(doc) if n == "input_menu" and p.get("id") == "PATCHVER")
    assert {next(iter(o)) for o in menu["options"]} == {"113c", "114d"}

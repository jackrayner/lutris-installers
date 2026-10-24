"""Checks every installer script in the repo against Lutris's rules."""

import re
import subprocess

import pytest
from lutris import (
    COMMANDS,
    VAR_RE,
    file_ids,
    file_urls,
    installer_paths,
    known_names,
    load,
    placeholder_values,
    steps,
    strings,
    substitute,
)

INSTALLERS = installer_paths()
IDS = [p.name for p in INSTALLERS]

REQUIRED_TOP_LEVEL = ["name", "game_slug", "version", "slug", "runner", "script"]


@pytest.fixture(params=INSTALLERS, ids=IDS)
def doc(request):
    return load(request.param)


def test_repo_has_installers():
    assert INSTALLERS


def test_required_fields(doc):
    for key in REQUIRED_TOP_LEVEL:
        assert doc.get(key), f"missing {key}"
    assert doc["script"].get("installer"), "no installer steps"
    assert doc["script"].get("game", {}).get("exe"), "no game exe"


def test_slug_is_lowercase_dashes(doc):
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", doc["slug"])
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", doc["game_slug"])


def test_steps_are_known_commands(doc):
    for i, name, params in steps(doc):
        assert name in COMMANDS, f"step {i}: unknown command {name}"
        assert params is not None, f"step {i}: {name} has no parameters"


def test_file_ids_unique(doc):
    ids = file_ids(doc)
    assert len(ids) == len(set(ids))


def _shell_assigned(command):
    names = set(re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)=", command))
    names |= set(re.findall(r"\bfor\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\b", command))
    return names


def _shell_text(name, params):
    """Shell code Lutris substitutes into: execute commands and written scripts."""
    if name == "execute":
        return params.get("command", "")
    if name == "write_file":
        return params.get("content", "")
    return ""


def test_variables_are_defined(doc):
    known = known_names(doc)
    for i, name, params in steps(doc):
        shell = _shell_text(name, params)
        local = _shell_assigned(shell)
        for text in strings(params):
            for var in VAR_RE.findall(text):
                if text is shell and var in local:
                    continue
                assert var in known, f"step {i} ({name}): ${var} is not defined"
    for text in strings(doc["script"]["game"]):
        for var in VAR_RE.findall(text):
            assert var in known, f"game: ${var} is not defined"


def test_shell_variables_dont_shadow_lutris_names(doc):
    # Lutris substitutes before the shell runs, so a shell variable sharing a
    # Lutris name would silently become that name's value
    known = known_names(doc)
    for i, name, params in steps(doc):
        clash = _shell_assigned(_shell_text(name, params)) & known
        assert not clash, f"step {i} ({name}): shell variables {sorted(clash)} shadow Lutris names"


def test_shell_commands_parse(doc):
    values = placeholder_values(doc)
    for i, name, params in steps(doc):
        if name == "execute" and "command" in params:
            script = substitute(params["command"], values)
            result = subprocess.run(["bash", "-n"], input=script, text=True, capture_output=True)
            assert result.returncode == 0, f"step {i}: {result.stderr}"


def test_downloads_are_checksummed(doc):
    variables = doc["script"].get("variables", {})
    checked = {
        params.get("args", "").split()[0]
        for _, name, params in steps(doc)
        if name == "execute" and "checkhash" in params.get("file", "") and params.get("args")
    }
    for file_id, url in file_urls(doc).items():
        if not url.startswith(("http://", "https://")):
            continue
        digest = variables.get(f"{file_id}_sha256", "")
        assert re.fullmatch(r"[0-9a-f]{64}", str(digest)), f"{file_id}: no {file_id}_sha256"
        assert file_id in checked, f"{file_id}: downloaded but never checksummed"


def test_user_files_have_prompts(doc):
    for file_id, url in file_urls(doc).items():
        if url.startswith("N/A"):
            assert url.startswith("N/A:") and len(url) > 4, f"{file_id}: no prompt text"


def test_input_menus_preselect_an_option(doc):
    for i, name, params in steps(doc):
        if name == "input_menu":
            options = [next(iter(o)) for o in params["options"]]
            assert len(options) == len(set(options)), f"step {i}: duplicate options"
            if "preselect" in params:
                assert str(params["preselect"]) in map(str, options), f"step {i}: bad preselect"

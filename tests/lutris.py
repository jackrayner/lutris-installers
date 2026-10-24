"""Just enough of Lutris's installer semantics to check scripts without Lutris.

Mirrors lutris/installer/interpreter.py and lutris/util/system.py (0.5.22):
variables are substituted with string.Template, a bare file id resolves to that
file's path, and command names may use dashes for underscores.
"""

import re
import string
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent

COMMANDS = {
    "chmodx", "execute", "extract", "input_menu", "insert_disc", "mkdir", "merge", "copy",
    "move", "rename", "substitute_vars", "task", "write_file", "write_json", "write_config",
    "autosetup_gog_game", "autosetup_zoom_platform", "autosetup_amazon", "install_or_extract",
}  # fmt: skip

BUILTINS = {
    "GAMEDIR", "SCRIPTDIR", "CACHE", "HOME", "STEAM_DATA_DIR", "DISC", "USER", "INPUT",
    "VERSION", "RESOLUTION", "RESOLUTION_WIDTH", "RESOLUTION_HEIGHT", "RESOLUTION_WIDTH_HEX",
    "RESOLUTION_HEIGHT_HEX", "WINEBIN",
}  # fmt: skip

VAR_RE = re.compile(r"\$\{?([A-Za-z_][A-Za-z0-9_-]*)\}?")


def installer_paths():
    return sorted(REPO.glob("*/installer.yml"))


def load(path):
    return yaml.safe_load(Path(path).read_text())


def steps(doc):
    """Yield (index, command_name, params) for each installer step."""
    for i, step in enumerate(doc["script"]["installer"]):
        ((name, params),) = step.items()
        yield i, name.replace("-", "_"), params


def file_ids(doc):
    return [next(iter(f)) for f in doc["script"].get("files", [])]


def file_urls(doc):
    return {k: v for f in doc["script"].get("files", []) for k, v in f.items()}


def input_ids(doc):
    return [p["id"] for _, name, p in steps(doc) if name == "input_menu" and "id" in p]


def known_names(doc):
    names = set(BUILTINS) | set(doc["script"].get("variables", {})) | set(file_ids(doc))
    names |= {f"INPUT_{i}" for i in input_ids(doc)}
    return names


def placeholder_values(doc):
    """Plausible stand-in values for every name Lutris would substitute."""
    values = {name: f"/lutris/{name}" for name in known_names(doc)}
    values.update(doc["script"].get("variables", {}))
    values["INPUT"] = "input"
    for name in list(values):
        if values[name] == f"/lutris/{name}" and name in file_ids(doc):
            values[name] = f"/lutris/cache/{name}/file"
    return values


def substitute(template, values):
    if template in values:
        return values[template]
    template = str(template)
    for name in values:
        template = template.replace(f"${name}", "$" + name.replace("-", "_"))
    values = {k.replace("-", "_"): v for k, v in values.items()}
    return string.Template(template).safe_substitute(values)


def strings(obj):
    """Every string value in a nested structure."""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from strings(v)

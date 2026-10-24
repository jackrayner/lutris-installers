"""Update the D2DX release pinned in the Diablo II installer.

Finds the newest release of the D2DX build repo, cross-checks the checksum of its
d2dx.zip from every source available, and rewrites the download URL and
d2dx_sha256 in the installer. Standard library only.

Exit status: 0 when the installer was updated or is already current, 1 when a release
can't be trusted or the installer isn't in the expected shape, 2 for bad arguments.
"""

import argparse
import hashlib
import io
import json
import os
import re
import sys
import urllib.request
import zipfile
from pathlib import Path

API = "https://api.github.com"
DEFAULT_REPO = "jackrayner/d2dx"
DEFAULT_FILE = Path(__file__).resolve().parent.parent / "diablo-ii-original-cds" / "installer.yml"
ASSET = "d2dx.zip"
DLL = "glide3x.dll"
MAX_ZIP_BYTES = 50 * 1024 * 1024

TAG_RE = re.compile(r"\d+\.\d+\.\d+")
SHA_RE = re.compile(r"[0-9a-f]{64}")
NOTES_SHA_RE = re.compile(r"d2dx\.zip[^\n]*?\b([0-9a-fA-F]{64})\b")
URL_LINE = re.compile(
    r"^(?P<head>\s*- d2dx: https://github\.com/)(?P<repo>[\w.-]+/[\w.-]+)"
    r"/releases/download/(?P<tag>[^/\s]+)/d2dx\.zip(?P<tail>[ \t]*)$",
    re.MULTILINE,
)
SHA_LINE = re.compile(
    r"^(?P<head>\s*d2dx_sha256:[ \t]*)(?P<sha>[0-9a-f]{64})(?P<tail>[ \t]*)$",
    re.MULTILINE,
)


class UpdateError(Exception):
    """A release can't be trusted, or the installer isn't in the expected shape."""


def version(tag):
    return tuple(int(part) for part in tag.split("."))


def newest_release(releases, include_prereleases=False):
    """The highest-versioned usable release, by version rather than by date."""
    usable = [
        r
        for r in releases
        if not r.get("draft")
        and (include_prereleases or not r.get("prerelease"))
        and TAG_RE.fullmatch(r.get("tag_name", ""))
        and any(a.get("name") == ASSET for a in r.get("assets", []))
    ]
    return max(usable, key=lambda r: version(r["tag_name"]), default=None)


def asset_of(release):
    return next(a for a in release["assets"] if a["name"] == ASSET)


def digest_from_asset(asset):
    value = asset.get("digest") or ""
    algorithm, _, hex_digest = value.partition(":")
    return (
        hex_digest.lower()
        if algorithm == "sha256" and SHA_RE.fullmatch(hex_digest.lower())
        else None
    )


def digest_from_notes(body):
    match = NOTES_SHA_RE.search(body or "")
    return match.group(1).lower() if match else None


def read_pin(text):
    """(repo, tag, sha) currently pinned in the installer."""
    urls, shas = URL_LINE.findall(text), SHA_LINE.findall(text)
    if len(urls) != 1 or len(shas) != 1:
        raise UpdateError(
            f"expected exactly one d2dx download line and one d2dx_sha256 line, "
            f"found {len(urls)} and {len(shas)}"
        )
    return urls[0][1], urls[0][2], shas[0][1]


def rewrite(text, tag, sha):
    text = URL_LINE.sub(
        lambda m: f"{m['head']}{m['repo']}/releases/download/{tag}/d2dx.zip{m['tail']}", text
    )
    return SHA_LINE.sub(lambda m: f"{m['head']}{sha}{m['tail']}", text)


def verify(release, data):
    """Check the downloaded zip against every other source. Returns the checks made."""
    asset = asset_of(release)
    actual = hashlib.sha256(data).hexdigest()
    if asset.get("size") is not None and asset["size"] != len(data):
        raise UpdateError(f"downloaded {len(data)} bytes, release says {asset['size']}")

    sources = {
        "GitHub's asset digest": digest_from_asset(asset),
        "the release notes": digest_from_notes(release.get("body")),
    }
    present = {name: sha for name, sha in sources.items() if sha}
    if not present:
        raise UpdateError(
            "no second checksum to compare with (no asset digest or release-notes checksum)"
        )
    for name, sha in present.items():
        if sha != actual:
            raise UpdateError(f"computed SHA-256 {actual} differs from {name}: {sha}")

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if DLL not in archive.namelist():
                raise UpdateError(f"{ASSET} has no top-level {DLL}, which the installer extracts")
    except zipfile.BadZipFile as error:
        raise UpdateError(f"{ASSET} is not a valid zip: {error}") from error

    return actual, sorted(present)


def pull_request_body(repo, old_tag, tag, old_sha, sha, checks):
    base = f"https://github.com/{repo}/releases/tag"
    paragraphs = [
        f"Update the pinned D2DX release from `{old_tag}` to `{tag}`.",
        "\n".join(
            [
                "| | Before | After |",
                "|---|---|---|",
                f"| Release | [{old_tag}]({base}/{old_tag}) | [{tag}]({base}/{tag}) |",
                f"| `d2dx_sha256` | `{old_sha}` | `{sha}` |",
            ]
        ),
        "Checked by the workflow:",
        "\n".join(
            [
                f"- the SHA-256 of the downloaded `{ASSET}`, computed here, matches "
                + " and ".join(checks),
                f"- the size matches the release, and the zip has a top-level `{DLL}`",
                "- the repository's tests pass with the updated installer",
            ]
        ),
        (
            "**Not checked:** CI can't run the game. Before merging, copy "
            f"`{DLL}` from the release into a Diablo II install, play for a few minutes, "
            "and check `d2dx_log.txt` and CPU use."
        ),
        (
            "Pull requests opened by `GITHUB_TOKEN` don't start other workflows, so the "
            "`Test` and `Lint` checks won't run on this PR; the tests were run in the "
            "update job instead."
        ),
        "\U0001f916 Generated with [Claude Code](https://claude.com/claude-code)",
    ]
    return "\n\n".join(paragraphs) + "\n"


def api_json(url):
    request = urllib.request.Request(
        url, headers={"Accept": "application/vnd.github+json", "User-Agent": "update-d2dx"}
    )
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def download(url, limit=MAX_ZIP_BYTES):
    # No Authorization header: the release is public, and the request is redirected to another host
    request = urllib.request.Request(url, headers={"User-Agent": "update-d2dx"})
    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise UpdateError(f"{url} is larger than {limit} bytes")
    return data


def write_outputs(**values):
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a") as out:
            out.writelines(f"{key}={value}\n" for key, value in values.items())


def run(args, get_json=api_json, get_bytes=download):
    installer = Path(args.file)
    text = installer.read_text()
    pinned_repo, old_tag, old_sha = read_pin(text)
    if pinned_repo != args.repo:
        raise UpdateError(f"the installer is pinned to {pinned_repo}, not {args.repo}")

    release = newest_release(
        get_json(f"{API}/repos/{args.repo}/releases?per_page=30"), args.include_prereleases
    )
    if release is None:
        print("No usable release found; leaving the installer alone.")
        write_outputs(changed="false")
        return
    tag = release["tag_name"]
    if version(tag) <= version(old_tag):
        print(f"Pinned {old_tag} is already the newest release ({tag}).")
        write_outputs(changed="false")
        return

    url = f"https://github.com/{args.repo}/releases/download/{tag}/{ASSET}"
    if asset_of(release).get("browser_download_url") != url:
        raise UpdateError(
            f"unexpected download URL for {tag}: {asset_of(release).get('browser_download_url')}"
        )
    sha, checks = verify(release, get_bytes(url))

    print(f"Updating {old_tag} -> {tag}, SHA-256 {sha} (matches {' and '.join(checks)}).")
    if not args.dry_run:
        installer.write_text(rewrite(text, tag, sha))
        if args.body_file:
            Path(args.body_file).write_text(
                pull_request_body(args.repo, old_tag, tag, old_sha, sha, checks)
            )
    write_outputs(changed="false" if args.dry_run else "true", tag=tag, old_tag=old_tag, sha256=sha)


def main(argv=None, **fetchers):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--repo", default=DEFAULT_REPO, help="owner/name of the D2DX build repo")
    parser.add_argument("--file", default=DEFAULT_FILE, help="installer YAML to update")
    parser.add_argument("--include-prereleases", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="check only; change nothing")
    parser.add_argument("--body-file", help="write the pull request description here")
    args = parser.parse_args(argv)
    try:
        run(args, **fetchers)
    except UpdateError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

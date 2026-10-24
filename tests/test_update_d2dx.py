import hashlib
import io
import zipfile

import pytest
import update_d2dx as u
from lutris import REPO

INSTALLER = REPO / "diablo-ii-original-cds" / "installer.yml"
REPO_NAME = "jackrayner/d2dx"


def make_zip(files=None):
    files = files or {"glide3x.dll": b"dll bytes", "README.md": b"readme"}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def url_for(tag):
    return f"https://github.com/{REPO_NAME}/releases/download/{tag}/d2dx.zip"


def make_release(tag, data, *, prerelease=False, draft=False, digest=True, notes=True, url=None):
    sha = hashlib.sha256(data).hexdigest()
    return {
        "tag_name": tag,
        "prerelease": prerelease,
        "draft": draft,
        "body": f"Release notes.\n\n`d2dx.zip` SHA-256: `{sha}`\n" if notes else "Release notes.",
        "assets": [
            {
                "name": "d2dx.zip",
                "size": len(data),
                "digest": f"sha256:{sha}" if digest else None,
                "browser_download_url": url or url_for(tag),
            }
        ],
    }


def install(tmp_path, tag="0.0.1", sha="a" * 64, repo=REPO_NAME):
    text = u.rewrite(INSTALLER.read_text(), tag, sha)
    text = text.replace(f"github.com/{REPO_NAME}/", f"github.com/{repo}/")
    path = tmp_path / "installer.yml"
    path.write_text(text)
    return path


def run_main(path, releases, zips, *extra):
    body = path.parent / "body.md"
    code = u.main(
        ["--file", str(path), "--body-file", str(body), *extra],
        get_json=lambda url: releases,
        get_bytes=lambda url: zips[url],
    )
    return code, body


@pytest.fixture(autouse=True)
def github_output(tmp_path, monkeypatch):
    out = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    return out


def outputs(path):
    return (
        dict(line.split("=", 1) for line in path.read_text().splitlines()) if path.exists() else {}
    )


def test_versions_compare_numerically():
    assert u.version("0.0.10") > u.version("0.0.9")
    assert u.version("0.10.0") > u.version("0.9.9")


def test_newest_release_is_highest_version_not_latest_published():
    data = make_zip()
    releases = [make_release(t, data) for t in ("0.0.2", "0.0.10", "0.0.3")]
    assert u.newest_release(releases)["tag_name"] == "0.0.10"


def test_newest_release_skips_unusable_releases():
    data = make_zip()
    no_asset = make_release("9.0.0", data)
    no_asset["assets"] = []
    releases = [
        make_release("5.0.0", data, draft=True),
        make_release("6.0.0", data, prerelease=True),
        make_release("v7.0.0", data),
        make_release("8.0.0-rc1", data),
        no_asset,
        make_release("0.0.1", data),
    ]
    assert u.newest_release(releases)["tag_name"] == "0.0.1"
    assert u.newest_release(releases, include_prereleases=True)["tag_name"] == "6.0.0"
    assert u.newest_release([]) is None


def test_asset_digest_only_trusts_sha256():
    sha = "ab" * 32
    assert u.digest_from_asset({"digest": f"sha256:{sha.upper()}"}) == sha
    assert u.digest_from_asset({"digest": f"sha512:{sha}"}) is None
    assert u.digest_from_asset({"digest": "sha256:short"}) is None
    assert u.digest_from_asset({}) is None


def test_notes_checksum_must_be_on_the_asset_line():
    sha = "cd" * 32
    assert u.digest_from_notes(f"`d2dx.zip` SHA-256: `{sha}`") == sha
    assert u.digest_from_notes(f"Commit {sha}\nunrelated") is None
    assert u.digest_from_notes(None) is None


def test_real_installer_is_pinned_to_the_fork():
    repo, tag, sha = u.read_pin(INSTALLER.read_text())
    assert repo == REPO_NAME
    assert u.TAG_RE.fullmatch(tag)
    assert u.SHA_RE.fullmatch(sha)


def test_read_pin_rejects_a_missing_or_duplicated_line():
    text = INSTALLER.read_text()
    with pytest.raises(u.UpdateError):
        u.read_pin(text.replace("d2dx_sha256:", "other_sha256:"))
    with pytest.raises(u.UpdateError):
        u.read_pin(text + "\n" + text)


def test_rewrite_changes_exactly_the_url_and_the_checksum():
    text = INSTALLER.read_text()
    new = u.rewrite(text, "9.9.9", "f" * 64)
    changed = [(a, b) for a, b in zip(text.splitlines(), new.splitlines(), strict=True) if a != b]
    assert len(changed) == 2
    assert u.read_pin(new) == (REPO_NAME, "9.9.9", "f" * 64)


def test_verify_accepts_a_release_every_source_agrees_on():
    data = make_zip()
    sha, checks = u.verify(make_release("0.0.2", data), data)
    assert sha == hashlib.sha256(data).hexdigest()
    assert checks == ["GitHub's asset digest", "the release notes"]


def test_verify_accepts_a_single_second_source():
    data = make_zip()
    assert u.verify(make_release("0.0.2", data, notes=False), data)[1] == ["GitHub's asset digest"]
    assert u.verify(make_release("0.0.2", data, digest=False), data)[1] == ["the release notes"]


def test_verify_refuses_when_nothing_can_cross_check():
    data = make_zip()
    with pytest.raises(u.UpdateError, match="no second checksum"):
        u.verify(make_release("0.0.2", data, digest=False, notes=False), data)


def test_verify_refuses_a_tampered_download():
    data = make_zip()
    release = make_release("0.0.2", data)
    with pytest.raises(u.UpdateError, match="differs from"):
        # Same size as the real zip, so only the checksum can catch it
        u.verify(release, make_zip({"glide3x.dll": b"dll bytez", "README.md": b"readme"}))


def test_verify_refuses_a_mismatch_with_either_source():
    data = make_zip()
    release = make_release("0.0.2", data)
    release["assets"][0]["digest"] = "sha256:" + "0" * 64
    with pytest.raises(u.UpdateError, match="asset digest"):
        u.verify(release, data)
    release = make_release("0.0.2", data)
    release["body"] = "`d2dx.zip` SHA-256: `" + "0" * 64 + "`"
    with pytest.raises(u.UpdateError, match="release notes"):
        u.verify(release, data)


def test_verify_refuses_a_size_mismatch():
    data = make_zip()
    release = make_release("0.0.2", data)
    release["assets"][0]["size"] += 1
    with pytest.raises(u.UpdateError, match="bytes"):
        u.verify(release, data)


def test_verify_needs_the_dll_at_the_top_level():
    for files in ({"nested/glide3x.dll": b"x"}, {"README.md": b"x"}):
        data = make_zip(files)
        with pytest.raises(u.UpdateError, match="top-level"):
            u.verify(make_release("0.0.2", data), data)


def test_verify_refuses_something_that_is_not_a_zip():
    data = b"not a zip"
    with pytest.raises(u.UpdateError, match="not a valid zip"):
        u.verify(make_release("0.0.2", data), data)


def test_update_rewrites_the_installer_and_writes_the_pr_body(tmp_path, github_output):
    path = install(tmp_path, "0.0.1")
    data = make_zip()
    code, body = run_main(path, [make_release("0.0.2", data)], {url_for("0.0.2"): data})
    sha = hashlib.sha256(data).hexdigest()
    assert code == 0
    assert u.read_pin(path.read_text()) == (REPO_NAME, "0.0.2", sha)
    text = body.read_text()
    assert "`0.0.1`" in text and "`0.0.2`" in text and sha in text
    assert "can't run the game" in text
    assert outputs(github_output) == {
        "changed": "true", "tag": "0.0.2", "old_tag": "0.0.1", "sha256": sha
    }  # fmt: skip


def test_up_to_date_changes_nothing(tmp_path, github_output):
    path = install(tmp_path, "0.0.2")
    before = path.read_text()
    data = make_zip()
    code, body = run_main(path, [make_release("0.0.2", data)], {})
    assert code == 0
    assert path.read_text() == before
    assert not body.exists()
    assert outputs(github_output) == {"changed": "false"}


def test_never_downgrades(tmp_path):
    path = install(tmp_path, "0.0.5")
    before = path.read_text()
    data = make_zip()
    assert run_main(path, [make_release("0.0.3", data)], {})[0] == 0
    assert path.read_text() == before


def test_prereleases_only_with_the_flag(tmp_path):
    data = make_zip()
    releases = [make_release("0.0.2", data, prerelease=True)]
    zips = {url_for("0.0.2"): data}
    path = install(tmp_path, "0.0.1")
    before = path.read_text()
    assert run_main(path, releases, zips)[0] == 0
    assert path.read_text() == before
    assert run_main(path, releases, zips, "--include-prereleases")[0] == 0
    assert u.read_pin(path.read_text())[1] == "0.0.2"


def test_dry_run_changes_nothing(tmp_path, github_output):
    path = install(tmp_path, "0.0.1")
    before = path.read_text()
    data = make_zip()
    code, body = run_main(
        path, [make_release("0.0.2", data)], {url_for("0.0.2"): data}, "--dry-run"
    )
    assert code == 0
    assert path.read_text() == before
    assert not body.exists()
    assert outputs(github_output)["changed"] == "false"


def test_failed_verification_fails_and_leaves_the_installer_alone(tmp_path):
    path = install(tmp_path, "0.0.1")
    before = path.read_text()
    data = make_zip()
    tampered = make_zip({"glide3x.dll": b"dll bytez", "README.md": b"readme"})
    code, body = run_main(path, [make_release("0.0.2", data)], {url_for("0.0.2"): tampered})
    assert code == 1
    assert path.read_text() == before
    assert not body.exists()


def test_refuses_an_installer_pinned_to_a_different_repo(tmp_path):
    path = install(tmp_path, "0.0.1", repo="bolrog/d2dx")
    before = path.read_text()
    data = make_zip()
    assert run_main(path, [make_release("0.0.2", data)], {url_for("0.0.2"): data})[0] == 1
    assert path.read_text() == before


def test_refuses_an_unexpected_download_url(tmp_path):
    path = install(tmp_path, "0.0.1")
    data = make_zip()
    release = make_release("0.0.2", data, url="https://example.com/d2dx.zip")
    assert run_main(path, [release], {url_for("0.0.2"): data})[0] == 1

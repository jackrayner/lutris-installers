"""Every script lives in its own folder with docs, and the index links to it."""

from lutris import REPO, installer_paths

NOT_SCRIPT_FOLDERS = {"tests", "scripts"}


def script_folders():
    return [
        p
        for p in sorted(REPO.iterdir())
        if p.is_dir() and not p.name.startswith((".", "_")) and p.name not in NOT_SCRIPT_FOLDERS
    ]


def test_no_installer_yaml_at_the_root():
    # The generic tests only look at <folder>/installer.yml, so a YAML file here would go unchecked
    assert not sorted(REPO.glob("*.yml"))


def test_every_script_folder_has_an_installer():
    for folder in script_folders():
        assert (folder / "installer.yml").is_file(), (
            f"{folder.name}/ has no installer.yml (other YAML files in it are not tested)"
        )


def test_every_script_folder_has_a_readme():
    for path in installer_paths():
        assert (path.parent / "README.md").is_file(), f"{path.parent.name}/ has no README.md"


def test_root_readme_links_every_script_folder():
    readme = (REPO / "README.md").read_text()
    for path in installer_paths():
        assert f"](./{path.parent.name}/)" in readme, f"README.md doesn't link {path.parent.name}/"

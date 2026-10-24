"""Guards for the GitHub Actions workflows themselves."""

import re

import pytest
import yaml
from lutris import REPO

WORKFLOWS = sorted((REPO / ".github" / "workflows").glob("*.yml"))
IDS = [p.name for p in WORKFLOWS]


@pytest.fixture(params=WORKFLOWS, ids=IDS)
def workflow(request):
    return yaml.safe_load(request.param.read_text())


def steps(workflow):
    return [s for job in workflow["jobs"].values() for s in job.get("steps", [])]


def test_declares_permissions(workflow):
    assert "permissions" in workflow, "set top-level permissions (least privilege)"


def test_run_steps_do_not_interpolate_expressions(workflow):
    # `${{ }}` in a run script is pasted in before the shell runs, so anything
    # attacker-influenced (branch names, release tags) could inject commands.
    # Pass values through `env:` and read them as shell variables instead.
    for step in steps(workflow):
        assert "${{" not in step.get("run", ""), f"expression in run: {step['run'][:60]}"


def test_actions_are_pinned_to_a_version(workflow):
    for step in steps(workflow):
        if "uses" in step:
            assert re.search(r"@(v\d|[0-9a-f]{40})", step["uses"]), f"unpinned: {step['uses']}"

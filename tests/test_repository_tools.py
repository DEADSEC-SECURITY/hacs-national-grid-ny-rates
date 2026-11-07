"""Guard dependency drift, unpinned workflows and accidental data publication."""

import json
import zipfile

import pytest

from tools.build_release import build
from tools.check_repository import check_pins, check_public_paths, check_workflows, runtime_pins


def test_runtime_pin_drift_requires_explicit_sync(tmp_path):
    requirements = tmp_path / "requirements.txt"
    manifest = tmp_path / "manifest.json"
    requirements.write_text("pypdf==6.13.3\n")
    manifest.write_text(json.dumps({"requirements": ["pypdf==6.13.2"]}))
    with pytest.raises(ValueError, match="pins differ"):
        check_pins(requirements, manifest)
    assert json.loads(manifest.read_text())["requirements"] == ["pypdf==6.13.2"]
    check_pins(requirements, manifest, sync=True)
    assert json.loads(manifest.read_text())["requirements"] == ["pypdf==6.13.3"]


def test_home_assistant_shared_dependency_uses_minimum_version(tmp_path):
    requirements = tmp_path / "requirements.txt"
    manifest = tmp_path / "manifest.json"
    requirements.write_text("beautifulsoup4==4.15.0\npypdf==6.21.4\n")
    manifest.write_text(json.dumps({"requirements": ["beautifulsoup4==4.15.0", "pypdf==6.21.4"]}))
    check_pins(requirements, manifest, sync=True)
    assert json.loads(manifest.read_text())["requirements"] == ["beautifulsoup4>=4.15.0", "pypdf==6.21.4"]
    check_pins(requirements, manifest)


@pytest.mark.parametrize(
    "value", ["pypdf>=6", "-r private.txt", "package @ https://example.org/code", "pypdf==6\npypdf==7"]
)
def test_invalid_runtime_requirements_fail(tmp_path, value):
    path = tmp_path / "requirements.txt"
    path.write_text(value)
    with pytest.raises(ValueError):
        runtime_pins(path)


def test_actions_must_be_pinned(tmp_path):
    path = tmp_path / "test.yml"
    path.write_text("steps:\n  - uses: actions/checkout@v7\n")
    with pytest.raises(ValueError, match="full commit"):
        check_workflows(tmp_path)


@pytest.mark.parametrize(
    "name", [".local/bill.json", "work/invoice.pdf", "customer.pdf", "secrets.yaml", ".env"]
)
def test_private_files_are_rejected(name):
    with pytest.raises(ValueError, match="must not be published"):
        check_public_paths([name])


def test_public_fixtures_allowed():
    check_public_paths(["tests/fixtures/public/sc.pdf", "custom_components/national_grid_ny_rates/sensor.py"])


def test_package_is_reproducible_and_excludes_private_data(tmp_path):
    integration = tmp_path / "custom_components/test_rates"
    integration.mkdir(parents=True)
    (integration / "manifest.json").write_text(json.dumps({"domain": "test_rates", "version": "1.2.3"}))
    for name in ("__init__.py", "sensor.py", "config_flow.py"):
        (integration / name).write_text("# public code\n")
    (integration / "secrets.yaml").write_text("do-not-package\n")
    (integration / "bill.pdf").write_text("do-not-package\n")
    (integration / "__pycache__").mkdir()
    (integration / "__pycache__/secret.py").write_text("do-not-package\n")
    first = build(integration, tmp_path / "one", tag="v1.2.3")
    second = build(integration, tmp_path / "two", tag="v1.2.3")
    assert first.read_bytes() == second.read_bytes()
    with zipfile.ZipFile(first) as archive:
        assert set(archive.namelist()) == {
            "test_rates/" + name for name in ("__init__.py", "manifest.json", "sensor.py", "config_flow.py")
        }
    with pytest.raises(ValueError, match="tag must match"):
        build(integration, tmp_path / "bad", tag="v1.2.4")

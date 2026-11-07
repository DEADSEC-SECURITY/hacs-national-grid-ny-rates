#!/usr/bin/env python3
"""Validate release metadata, runtime pins, Actions pins and public file scope."""

import argparse
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "national_grid_ny_rates"
ENTITIES = {"delivery", "supply", "tax", "total_before_tax", "total_including_tax"}


def runtime_pins(path: Path) -> list[str]:
    pins = []
    for line in path.read_text().splitlines():
        value = line.split("#", 1)[0].strip()
        if not value:
            continue
        if not re.fullmatch(r"[A-Za-z0-9_.-]+==[A-Za-z0-9_.+-]+", value):
            raise ValueError("Runtime requirements must be exact, registry-based pins")
        pins.append(value)
    if not pins or len(pins) != len(set(pin.split("==")[0].lower() for pin in pins)):
        raise ValueError("Missing or duplicate runtime dependencies")
    return pins


def check_pins(requirements: Path, manifest: Path, sync: bool = False) -> None:
    pins = runtime_pins(requirements)
    data = json.loads(manifest.read_text())
    if data["requirements"] != pins:
        if not sync:
            raise ValueError(
                "Runtime pins differ from the HA manifest; review the update, then run tools/check_repository.py --sync-runtime"
            )
        data["requirements"] = pins
        manifest.write_text(json.dumps(data, indent=2) + "\n")


def check_workflows(folder: Path) -> None:
    for path in folder.glob("*.y*ml"):
        for action in re.findall(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)", path.read_text(), re.M):
            if action.startswith("./.github/workflows/"):
                continue
            if not re.fullmatch(r"[A-Za-z0-9_./-]+@[a-f0-9]{40}", action):
                raise ValueError(f"{path.name}: external Actions must use full commit SHAs: {action}")


def check_public_paths(paths: list[str]) -> None:
    for name in paths:
        path = Path(name)
        if (
            set(path.parts) & {".local", ".aws", ".codex", ".agents", ".venv", "work", "outputs"}
            or path.name in {"secrets.yaml", "configuration.yaml", ".env", ".coverage"}
            or path.name.startswith(".env.")
            or (path.suffix.lower() == ".pdf" and path.parts[:3] != ("tests", "fixtures", "public"))
        ):
            raise ValueError(f"Private/development file must not be published: {name}")


def main(sync: bool = False) -> None:
    check_pins(ROOT / "requirements.txt", INTEGRATION / "manifest.json", sync)
    manifest = json.loads((INTEGRATION / "manifest.json").read_text())
    hacs = json.loads((ROOT / "hacs.json").read_text())
    assert manifest["domain"] == INTEGRATION.name
    assert manifest["config_flow"] is True
    assert re.fullmatch(r"\d+\.\d+\.\d+(?:[a-z0-9.-]*)", manifest["version"])
    assert hacs["name"] == manifest["name"]
    assert len(list((ROOT / "custom_components").glob("*/manifest.json"))) == 1
    strings = json.loads((INTEGRATION / "strings.json").read_text())
    assert set(strings["entity"]["sensor"]) == ENTITIES
    assert json.loads((INTEGRATION / "translations/en.json").read_text()) == strings
    check_workflows(ROOT / ".github/workflows")
    files = (
        subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=ROOT,
        )
        .decode()
        .split("\0")
    )
    check_public_paths([name for name in files if name])
    print("Metadata, five entities, runtime pins, Actions pins and public file scope verified")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sync-runtime", action="store_true")
    main(parser.parse_args().sync_runtime)

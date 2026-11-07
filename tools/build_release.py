#!/usr/bin/env python3
"""Build a reproducible integration-only ZIP, excluding all private/test data."""

import argparse
import hashlib
import json
import os
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build(integration: Path, output: Path, tag: str | None = None) -> Path:
    manifest = json.loads((integration / "manifest.json").read_text())
    if tag and tag != "v" + manifest["version"]:
        raise ValueError("Release tag must match the Home Assistant manifest version")
    output.mkdir(parents=True, exist_ok=True)
    package = output / (manifest["domain"] + ".zip")
    files = sorted(
        path
        for path in integration.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix in {".py", ".json", ".png", ".yaml", ".yml"}
        and path.name not in {"configuration.yaml", "secrets.yaml"}
    )
    required = {
        integration / name for name in ("__init__.py", "manifest.json", "sensor.py", "config_flow.py")
    }
    if not required.issubset(files):
        raise ValueError("Install package is missing required integration files")
    with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            name = path.relative_to(integration.parent).as_posix()
            info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    with zipfile.ZipFile(package) as archive:
        if archive.testzip():
            raise ValueError("Install package failed CRC verification")
    digest = hashlib.sha256(package.read_bytes()).hexdigest()
    (output / "SHA256SUMS").write_text(digest + "  " + package.name + "\n")
    print(f"Built {package.name}: {len(files)} integration files, SHA256 {digest}")
    return package


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    tag = os.environ.get("GITHUB_REF_NAME") if os.environ.get("GITHUB_REF_TYPE") == "tag" else None
    build(ROOT / "custom_components/national_grid_ny_rates", args.output_dir, tag)

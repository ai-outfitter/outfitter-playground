"""Validate the JLCPCB package and write or verify its SHA-256 manifest."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
FAB = HERE / "fab"
MANIFEST = FAB / "manifest.json"
REQUIRED = [
    "pnb-1-gerbers.zip",
    "bom.csv",
    "cpl.csv",
    "front.png",
    "back.png",
    "pnb-1-drc.json",
]
BOM_COLUMNS = {"Comment", "Designator", "Footprint", "LCSC Part #"}
CPL_COLUMNS = {"Designator", "Mid X", "Mid Y", "Rotation", "Layer"}
ALLOWED_DRC = {"silk_over_copper", "silk_overlap", "silk_edge_clearance"}


def rows(path: Path, columns: set[str]) -> list[dict[str, str]]:
    with path.open(newline="") as source:
        parsed = list(csv.DictReader(source))
    assert parsed, f"{path.name} is empty"
    assert set(parsed[0]) == columns, f"{path.name} columns are {set(parsed[0])}"
    for row in parsed:
        assert all(row[column].strip() for column in columns), f"blank field in {path.name}: {row}"
    return parsed


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate() -> dict[str, object]:
    for name in REQUIRED:
        assert (FAB / name).is_file(), f"missing fab/{name}"

    bom = rows(FAB / "bom.csv", BOM_COLUMNS)
    cpl = rows(FAB / "cpl.csv", CPL_COLUMNS)
    bom_refs = {ref for row in bom for ref in row["Designator"].replace('"', "").split(",")}
    cpl_refs = {row["Designator"].replace('"', "") for row in cpl}
    assert cpl_refs <= bom_refs, f"CPL references absent from BOM: {sorted(cpl_refs - bom_refs)}"
    assert bom_refs - cpl_refs <= {"J3", "J4"}, f"populated BOM refs absent from CPL: {sorted(bom_refs-cpl_refs)}"

    with ZipFile(FAB / "pnb-1-gerbers.zip") as archive:
        suffixes = {Path(name).suffix.lower() for name in archive.namelist()}
    required_suffixes = {".gtl", ".gbl", ".gts", ".gbs", ".gm1", ".drl"}
    assert required_suffixes <= suffixes, f"Gerber ZIP missing {sorted(required_suffixes-suffixes)}"

    drc = json.loads((FAB / "pnb-1-drc.json").read_text())
    assert not drc.get("unconnected_items"), "DRC has unconnected items"
    unexpected = {item["type"] for item in drc.get("violations", [])} - ALLOWED_DRC
    assert not unexpected, f"unexpected DRC violations: {sorted(unexpected)}"

    return {
        "schemaVersion": 1,
        "board": "PNB-1 rev A",
        "source": "pnb1_skidl.py -> pnb-1.net -> build.py -> route.py -> pnb-1.kibot.yaml",
        "bomRows": len(bom),
        "placements": len(cpl),
        "drcWarnings": len(drc.get("violations", [])),
        "files": {
            name: {"bytes": (FAB / name).stat().st_size, "sha256": sha256(FAB / name)}
            for name in REQUIRED
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    actual = validate()
    if args.write:
        MANIFEST.write_text(json.dumps(actual, indent=2, sort_keys=True) + "\n")
    else:
        expected = json.loads(MANIFEST.read_text())
        assert actual == expected, "fabrication manifest does not match package"
    print(f"package: {actual['bomRows']} BOM rows, {actual['placements']} placements, manifest valid")


if __name__ == "__main__":
    main()

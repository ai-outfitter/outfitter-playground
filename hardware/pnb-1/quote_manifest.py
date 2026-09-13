"""Verify that the committed supplier evidence is a complete landed-cost quote."""

from __future__ import annotations

import csv
import hashlib
import json
from decimal import Decimal
from pathlib import Path


HERE = Path(__file__).resolve().parent
FAB = HERE / "fab"
QUOTE = FAB / "supplier-quote.json"
COST_CATEGORIES = {
    "pcbFabrication",
    "components",
    "assembly",
    "setupTooling",
    "shipping",
    "tariffDuty",
    "tax",
    "discounts",
    "otherFees",
}
REQUIRED_PARTS = {"U1", "U3", "U4"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def designators() -> set[str]:
    with (FAB / "bom.csv").open(newline="") as source:
        rows = csv.DictReader(source)
        return {
            ref.strip()
            for row in rows
            for ref in row["Designator"].replace('"', "").split(",")
        }


def verify() -> dict[str, object]:
    quote = json.loads(QUOTE.read_text())
    assert quote["schemaVersion"] == 1
    assert quote["verdict"] == "quote-complete"
    assert quote["supplier"] == "JLCPCB"
    assert quote["currency"] == "USD"
    assert quote["quoteId"] and quote["quotedAt"]
    assert quote["quantities"]["pcb"] > 0
    assert quote["quantities"]["assembly"] > 0

    destination = quote["destination"]
    assert destination["country"] and destination["postalRegion"]
    assert quote["shippingMethod"] and quote["incoterm"]

    manifest = json.loads((FAB / "manifest.json").read_text())
    package = quote["package"]
    assert package["manifestSha256"] == sha256(FAB / "manifest.json")
    for name in ("pnb-1-gerbers.zip", "bom.csv", "cpl.csv"):
        assert package["files"][name] == manifest["files"][name]["sha256"]

    expected = designators()
    matched = set(quote["matching"]["matchedDesignators"])
    assert matched == expected, f"supplier match differs from fitted BOM: {sorted(expected ^ matched)}"
    assert REQUIRED_PARTS <= matched, "ESP32-S3, SCD41, and BH1750 must all be supplier-matched"
    assert quote["matching"]["missingDesignators"] == []
    assert quote["matching"]["unavailableDesignators"] == []
    assert all(item.get("approved") is True for item in quote["matching"]["substitutions"])

    costs = quote["costs"]
    assert set(costs) == COST_CATEGORIES
    total = Decimal("0")
    for category, item in costs.items():
        status = item["status"]
        amount = Decimal(item["amount"])
        assert status in {"quoted", "included"}, f"{category} cost is incomplete: {status}"
        assert item["evidence"], f"{category} has no evidence reference"
        if status == "included":
            assert amount == 0 and item.get("includedIn") in COST_CATEGORIES - {category}
        else:
            total += amount
    assert total == Decimal(quote["landedTotal"]), f"cost lines total {total}, not {quote['landedTotal']}"

    evidence = quote["evidence"]
    evidence_hashes = quote["evidenceSha256"]
    assert set(evidence_hashes) == set(evidence.values())
    for name in (
        "boardPreview",
        "partsMatch",
        "placementPreview",
        "assemblyQuote",
        "shippingMethod",
        "landedCost",
    ):
        path = FAB / evidence[name]
        assert path.is_file() and path.stat().st_size > 0, f"missing quote evidence: {path.name}"
        assert evidence_hashes[path.name] == sha256(path), f"quote evidence changed: {path.name}"

    return quote


if __name__ == "__main__":
    verified = verify()
    print(
        "quote: "
        f"{len(verified['matching']['matchedDesignators'])} fitted designators, "
        f"{verified['currency']} {verified['landedTotal']} landed, complete"
    )

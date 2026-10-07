"""Load operator-owned SKU economics from a portable CSV contract."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import List

from launchguard.models import SkuEvidence


def load_catalog(path: Path) -> List[SkuEvidence]:
    if not path.exists():
        raise FileNotFoundError(f"Catalog does not exist: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError("Catalog must contain at least one SKU row")
    return [SkuEvidence.model_validate(row) for row in rows]


def load_sku(path: Path, sku: str) -> SkuEvidence:
    normalized = sku.upper().replace(" ", "-")
    matches = [item for item in load_catalog(path) if item.sku == normalized]
    if not matches:
        raise ValueError(f"SKU {normalized!r} was not found in {path}")
    if len(matches) > 1:
        raise ValueError(f"SKU {normalized!r} appears more than once in {path}")
    return matches[0]

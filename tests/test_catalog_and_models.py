from pathlib import Path

import pytest
from pydantic import ValidationError

from launchguard.connectors.catalog import load_catalog, load_sku
from launchguard.models import ApprovalDecision, SkuEvidence


def test_catalog_loads_operator_evidence() -> None:
    catalog = Path(__file__).parents[1] / "examples" / "catalog.csv"
    rows = load_catalog(catalog)
    assert len(rows) == 2
    assert rows[0].sku == "LG-BTL-001"
    assert rows[0].source_reference.startswith("supplier-quote")


def test_catalog_selects_one_sku() -> None:
    catalog = Path(__file__).parents[1] / "examples" / "catalog.csv"
    assert load_sku(catalog, "lg-lamp-002").title == "Rechargeable Reading Lamp"
    with pytest.raises(ValueError, match="was not found"):
        load_sku(catalog, "missing")


def test_catalog_rejects_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "empty.csv"
    path.write_text("sku,title\n", encoding="utf-8")
    with pytest.raises(ValueError, match="at least one"):
        load_catalog(path)


def test_sku_contract_normalizes_and_forbids_unknown_fields(sku: SkuEvidence) -> None:
    assert sku.sku == "TEST-BOTTLE-001"
    payload = sku.model_dump()
    payload["secret_extra"] = "not allowed"
    with pytest.raises(ValidationError):
        SkuEvidence.model_validate(payload)


def test_approval_contract_requires_named_reviewer() -> None:
    with pytest.raises(ValidationError):
        ApprovalDecision(action="approve", reviewer="x")

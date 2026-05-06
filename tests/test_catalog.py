"""Provider catalog tests."""
from __future__ import annotations

import pytest

from provider.catalog import CATALOG_BY_ID, get_catalog_with_availability, make_quote


@pytest.mark.parametrize("tier", ["small", "medium", "large"])
def test_catalog_advertises_each_tier(tier):
    catalog = get_catalog_with_availability()
    pkg = next((p for p in catalog if p["packageId"] == tier), None)
    assert pkg is not None
    assert pkg["mbps"] <= 10  # PPS cap on free SR Linux
    assert pkg["priceWei"] > 0
    assert pkg["availableSlots"] >= 0
    assert tier in CATALOG_BY_ID


def test_make_quote_returns_agreement_data():
    result = make_quote("small",
                        "0x0000000000000000000000000000000000000001")
    assert result is not None
    assert "agreementId" in result
    assert result["priceWei"] > 0


def test_make_quote_unknown_package():
    assert make_quote("nonexistent",
                      "0x0000000000000000000000000000000000000001") is None

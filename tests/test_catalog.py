import pytest
from provider.catalog import get_catalog_with_availability, CATALOG_BY_ID, make_quote


def test_catalog_has_three_tiers():
    catalog = get_catalog_with_availability()
    assert len(catalog) == 3
    tiers = {p["packageId"] for p in catalog}
    assert tiers == {"small", "medium", "large"}


def test_catalog_has_required_fields():
    catalog = get_catalog_with_availability()
    for p in catalog:
        assert "packageId" in p
        assert "mbps" in p
        assert "priceWei" in p
        assert "availableSlots" in p
        assert p["availableSlots"] >= 0


def test_catalog_by_id_has_all_tiers():
    assert "small" in CATALOG_BY_ID
    assert "medium" in CATALOG_BY_ID
    assert "large" in CATALOG_BY_ID


def test_make_quote_returns_agreement_data():
    result = make_quote("small", "0x0000000000000000000000000000000000000001")
    assert result is not None
    assert "agreementId" in result
    assert "priceWei" in result
    assert "bandwidthMbps" in result
    assert "durationSeconds" in result
    assert result["priceWei"] > 0


def test_make_quote_unknown_package():
    result = make_quote("nonexistent", "0x0000000000000000000000000000000000000001")
    assert result is None

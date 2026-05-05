import json
import time
from pathlib import Path

import pytest

from shared.slot_pool import SlotPool, Slot


@pytest.fixture
def tmp_inventory(tmp_path: Path) -> Path:
    f = tmp_path / "inventory.txt"
    rows = [
        {"tier": "small", "mbps": 2, "durationSeconds": 600, "slots": [
            {"pe": "pe1", "subinterface": "ethernet-1/2.0", "ce": "ce1",
             "agreementId": None, "expiresAt": None}
        ]},
        {"tier": "medium", "mbps": 5, "durationSeconds": 600, "slots": [
            {"pe": "pe1", "subinterface": "ethernet-1/3.0", "ce": "ce3",
             "agreementId": None, "expiresAt": None}
        ]},
    ]
    with open(f, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    return f


def test_available_slots_initial(tmp_inventory):
    pool = SlotPool(tmp_inventory)
    assert pool.available_count("small") == 1
    assert pool.available_count("medium") == 1
    assert pool.available_count("nonexistent") == 0


def test_reserve_binds_slot_to_agreement(tmp_inventory):
    pool = SlotPool(tmp_inventory)
    slot = pool.reserve("small", agreement_id=42, duration_seconds=600)
    assert slot is not None
    assert slot.pe == "pe1"
    assert slot.subinterface == "ethernet-1/2.0"
    assert slot.ce == "ce1"
    assert pool.available_count("small") == 0


def test_reserve_returns_none_when_full(tmp_inventory):
    pool = SlotPool(tmp_inventory)
    pool.reserve("small", agreement_id=42, duration_seconds=600)
    second = pool.reserve("small", agreement_id=43, duration_seconds=600)
    assert second is None


def test_release_frees_slot(tmp_inventory):
    pool = SlotPool(tmp_inventory)
    pool.reserve("small", agreement_id=42, duration_seconds=600)
    assert pool.available_count("small") == 0
    pool.release(agreement_id=42)
    assert pool.available_count("small") == 1


def test_lookup_returns_slot_for_agreement(tmp_inventory):
    pool = SlotPool(tmp_inventory)
    pool.reserve("medium", agreement_id=99, duration_seconds=600)
    slot = pool.lookup(99)
    assert slot is not None
    assert slot.pe == "pe1"
    assert slot.subinterface == "ethernet-1/3.0"
    assert slot.ce == "ce3"


def test_expired_slots_are_reclaimed_on_read(tmp_inventory):
    pool = SlotPool(tmp_inventory)
    pool.reserve("small", agreement_id=42, duration_seconds=1)
    time.sleep(1.5)
    pool2 = SlotPool(tmp_inventory)
    assert pool2.available_count("small") == 1

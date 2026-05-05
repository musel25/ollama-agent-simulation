"""HTTP-level tests for consumer/app.py routes that mock web3."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("CONSUMER_PRIVATE_KEY",
                       "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a")
    from consumer.app import app
    with TestClient(app) as c:
        yield c


def test_chain_events_returns_combined_events(client, monkeypatch):
    from consumer import app as consumer_app

    fake_escrow = MagicMock()
    fake_escrow.events.AgreementRequested.get_logs.return_value = []
    fake_escrow.events.Deposit.get_logs.return_value = []
    fake_nft = MagicMock()
    fake_nft.events.Transfer.get_logs.return_value = []

    fake_w3 = MagicMock()
    fake_w3.eth.block_number = 100
    fake_w3.eth.get_transaction_receipt.return_value = {"gasUsed": 50_000}

    monkeypatch.setattr(consumer_app, "_w3", fake_w3)
    monkeypatch.setattr(consumer_app, "get_escrow_contract", lambda w3: fake_escrow)
    monkeypatch.setattr(consumer_app, "get_nft_contract", lambda w3: fake_nft)

    resp = client.get("/chain_events", params={"since_block": 0})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert data == []  # no events in this synthetic chain

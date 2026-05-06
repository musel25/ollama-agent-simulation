"""Shared pytest fixtures."""
from __future__ import annotations

import pytest

from shared.config import Config


CONSUMER_KEY = "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a"
PROVIDER_KEY = "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"
DEPLOYER_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"


@pytest.fixture
def consumer_cfg() -> Config:
    return Config(consumer_private_key=CONSUMER_KEY)


@pytest.fixture
def provider_cfg() -> Config:
    return Config(provider_private_key=PROVIDER_KEY, sdn_mock=True)


@pytest.fixture
def fake_catalog() -> list[dict]:
    return [
        {"packageId": "small",  "mbps": 2.0, "durationSeconds": 600,
         "priceWei": 10**16, "availableSlots": 1},
        {"packageId": "medium", "mbps": 5.0, "durationSeconds": 600,
         "priceWei": 2 * 10**16, "availableSlots": 1},
        {"packageId": "large",  "mbps": 8.0, "durationSeconds": 600,
         "priceWei": 8 * 10**16, "availableSlots": 1},
    ]

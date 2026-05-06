"""Tests for shared.config.Config."""
from __future__ import annotations

import os
from unittest.mock import patch

from shared.config import Config


def test_from_env_reads_known_vars():
    env = {
        "RPC_URL": "http://anvil:8545",
        "OLLAMA_HOST": "http://ollama:11434",
        "OLLAMA_MODEL": "llama3.2:3b",
        "CONSUMER_PRIVATE_KEY": "0xaaaa",
        "PROVIDER_PRIVATE_KEY": "0xbbbb",
        "DEPLOYER_PRIVATE_KEY": "0xcccc",
        "SDN_MOCK": "false",
    }
    with patch.dict(os.environ, env, clear=True):
        cfg = Config.from_env()
    assert cfg.rpc_url == "http://anvil:8545"
    assert cfg.ollama_host == "http://ollama:11434"
    assert cfg.ollama_model == "llama3.2:3b"
    assert cfg.consumer_private_key == "0xaaaa"
    assert cfg.provider_private_key == "0xbbbb"
    assert cfg.deployer_private_key == "0xcccc"
    assert cfg.sdn_mock is False


def test_from_env_uses_defaults_when_unset():
    with patch.dict(os.environ, {}, clear=True):
        cfg = Config.from_env()
    assert cfg.rpc_url == "http://localhost:8545"
    assert cfg.ollama_host == "http://localhost:11434"
    assert cfg.ollama_model == "llama3.2:3b"
    assert cfg.consumer_private_key is None
    assert cfg.provider_private_key is None
    assert cfg.deployer_private_key is None
    assert cfg.sdn_mock is True


def test_config_is_frozen():
    import pytest
    cfg = Config()
    with pytest.raises(Exception):
        cfg.rpc_url = "http://x"  # type: ignore[misc]

"""End-to-end test: spin Anvil, deploy contracts, run a full negotiation
in-process between the consumer and provider FastAPI apps with a stubbed LLM.

Skipped if the `anvil` or `forge` binaries are not on PATH.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import socket
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest
import uvicorn
from eth_account import Account

from shared.anvil import anvil
from shared.config import Config
from shared.deploy import deploy_contracts


pytestmark = pytest.mark.skipif(
    shutil.which("anvil") is None or shutil.which("forge") is None,
    reason="anvil/forge required for the end-to-end test",
)


CONSUMER_KEY = "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a"
PROVIDER_KEY = "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"
DEPLOYER_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"


@pytest.fixture(autouse=True)
def _restore_inventory():
    """Snapshot provider/inventory.txt and restore it after the test so the
    on-disk SlotPool state never leaks between test runs."""
    inv = Path(__file__).resolve().parent.parent / "provider" / "inventory.txt"
    original = inv.read_bytes()
    try:
        yield
    finally:
        inv.write_bytes(original)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _serve(app, port: int) -> tuple[uvicorn.Server, threading.Thread]:
    cfg = uvicorn.Config(app, host="127.0.0.1", port=port,
                         log_level="warning", lifespan="on")
    server = uvicorn.Server(cfg)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    # Wait for startup
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and not server.started:
        time.sleep(0.05)
    return server, thread


def _stop(server: uvicorn.Server, thread: threading.Thread) -> None:
    server.should_exit = True
    thread.join(timeout=5)


@pytest.mark.asyncio
async def test_end_to_end_negotiation_settles_on_chain(monkeypatch):
    """Drives the full discover → quote → lock → settle → present → verify
    flow against an in-process Anvil + provider + consumer, with the LLM
    stubbed so we never depend on Ollama."""
    # Stub the LLM
    from langchain_ollama import ChatOllama

    class _R:
        def __init__(self, c): self.content = c

    async def fake_ainvoke(self, prompt, *a, **kw):
        return _R("medium" if "EXACTLY ONE WORD" in prompt else "ok.")

    monkeypatch.setattr(ChatOllama, "ainvoke", fake_ainvoke)

    with anvil(port=18545) as rpc_url:
        cfg = Config(
            rpc_url=rpc_url,
            consumer_private_key=CONSUMER_KEY,
            provider_private_key=PROVIDER_KEY,
            deployer_private_key=DEPLOYER_KEY,
            sdn_mock=True,
        )
        # Deploy contracts
        deploy_contracts(cfg)

        provider_port = _free_port()
        consumer_port = _free_port()
        provider_url = f"http://127.0.0.1:{provider_port}"
        consumer_url = f"http://127.0.0.1:{consumer_port}"

        # Build the apps with overridden env so they pick up `cfg`.
        monkeypatch.setenv("RPC_URL", rpc_url)
        monkeypatch.setenv("CONSUMER_PRIVATE_KEY", CONSUMER_KEY)
        monkeypatch.setenv("PROVIDER_PRIVATE_KEY", PROVIDER_KEY)
        monkeypatch.setenv("PROVIDER_BASE_URL", provider_url)
        monkeypatch.setenv("CONSUMER_BASE_URL", consumer_url)
        monkeypatch.setenv("PROVIDER_A2A_URLS", provider_url)
        monkeypatch.setenv("SDN_MOCK", "true")

        from provider.app import app as provider_app
        from consumer.app import app as consumer_app

        ps, pt = _serve(provider_app, provider_port)
        try:
            cs, ct = _serve(consumer_app, consumer_port)
            try:
                async with httpx.AsyncClient(timeout=120.0) as http:
                    resp = await http.post(f"{consumer_url}/chat",
                                           json={"message": "I need 5 Mbps"})
                    resp.raise_for_status()
                    body = resp.json()
                assert "Active service" in body["response"]
            finally:
                _stop(cs, ct)
        finally:
            _stop(ps, pt)

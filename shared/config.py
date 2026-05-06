"""Single source of runtime configuration for both agents.

Every module that previously called `os.getenv(...)` now accepts a
`Config` instance. Notebooks construct one explicitly; the FastAPI apps
build one in their `lifespan` via `Config.from_env()`.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    rpc_url: str = "http://localhost:8545"
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"
    consumer_private_key: str | None = None
    provider_private_key: str | None = None
    deployer_private_key: str | None = None
    provider_address: str | None = None
    consumer_base_url: str = "http://localhost:8001"
    provider_base_url: str = "http://localhost:8002"
    provider_a2a_urls: tuple[str, ...] = ("http://localhost:8002",)
    sdn_mock: bool = True

    @classmethod
    def from_env(cls) -> "Config":
        """Build a `Config` by reading the standard environment variables."""
        urls_raw = os.environ.get(
            "PROVIDER_A2A_URLS",
            os.environ.get("PROVIDER_BASE_URL", "http://localhost:8002"),
        )
        urls = tuple(u.strip() for u in urls_raw.split(",") if u.strip())
        return cls(
            rpc_url=os.environ.get("RPC_URL", cls.rpc_url),
            ollama_host=os.environ.get("OLLAMA_HOST", cls.ollama_host),
            ollama_model=os.environ.get("OLLAMA_MODEL", cls.ollama_model),
            consumer_private_key=os.environ.get("CONSUMER_PRIVATE_KEY"),
            provider_private_key=os.environ.get("PROVIDER_PRIVATE_KEY"),
            deployer_private_key=os.environ.get("DEPLOYER_PRIVATE_KEY"),
            provider_address=os.environ.get("PROVIDER_ADDRESS"),
            consumer_base_url=os.environ.get(
                "CONSUMER_BASE_URL", cls.consumer_base_url
            ),
            provider_base_url=os.environ.get(
                "PROVIDER_BASE_URL", cls.provider_base_url
            ),
            provider_a2a_urls=urls,
            sdn_mock=os.environ.get("SDN_MOCK", "true").lower() == "true",
        )

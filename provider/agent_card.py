"""
Builds the a2a.types.AgentCard for the bandwidth provider agent.

a2a-sdk uses protobuf-generated types; constructors take kwargs matching
the proto field names. Use google.protobuf.json_format.MessageToDict to
serialize the card to JSON for the .well-known endpoint.
"""
from __future__ import annotations

import os

from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
)

PROVIDER_BASE_URL = os.environ.get("PROVIDER_BASE_URL", "http://localhost:8002")
A2A_RPC_URL = f"{PROVIDER_BASE_URL}/a2a"


def build_provider_agent_card() -> AgentCard:
    return AgentCard(
        name="Bandwidth Provider Agent",
        description=(
            "Sells time-bound bandwidth packages via atomic on-chain escrow + "
            "ERC-721 credential. Activates SDN policy (gNMI policer + tc rate-limit) "
            "on credential presentation."
        ),
        version="2.0.0",
        default_input_modes=["application/json", "text/plain"],
        default_output_modes=["application/json"],
        capabilities=AgentCapabilities(streaming=False, extended_agent_card=False),
        supported_interfaces=[
            AgentInterface(protocol_binding="JSONRPC", url=A2A_RPC_URL),
        ],
        skills=[
            AgentSkill(
                id="get_catalog",
                name="Get Catalog",
                description="Returns available bandwidth tiers with pricing and availability.",
                tags=["bandwidth", "catalog"],
                examples=['{"action": "get_catalog"}'],
            ),
            AgentSkill(
                id="request_quote",
                name="Request Quote",
                description=(
                    "Issues an agreementId-bound price quote for a chosen tier. "
                    "Required input: package_id (small|medium|large), consumer_address."
                ),
                tags=["bandwidth", "quote", "escrow"],
                examples=[
                    '{"action": "request_quote", "package_id": "medium", "consumer_address": "0x..."}'
                ],
            ),
            AgentSkill(
                id="activate",
                name="Activate Service",
                description=(
                    "Verifies NFT credential ownership (signature over nonce + on-chain "
                    "ownerOf check) and triggers SDN allocation for the bound resource slot."
                ),
                tags=["bandwidth", "activation", "sdn"],
                examples=[
                    '{"action": "activate", "token_id": 7, "nonce": "1730000000", "signature": "0x..."}'
                ],
            ),
        ],
    )

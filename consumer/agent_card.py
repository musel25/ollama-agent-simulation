"""AgentCard for the consumer agent."""
from __future__ import annotations

import os

from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
)

CONSUMER_BASE_URL = os.environ.get("CONSUMER_BASE_URL", "http://localhost:8001")


def build_consumer_agent_card() -> AgentCard:
    return AgentCard(
        name="Bandwidth Consumer Agent",
        description=(
            "Autonomously procures time-bound bandwidth from provider agents via "
            "atomic on-chain escrow + ERC-721 credential."
        ),
        version="2.0.0",
        default_input_modes=["text/plain"],
        default_output_modes=["application/json", "text/plain"],
        capabilities=AgentCapabilities(streaming=False, extended_agent_card=False),
        supported_interfaces=[
            AgentInterface(
                protocol_binding="HTTP",
                url=f"{CONSUMER_BASE_URL}/chat",
            ),
        ],
        skills=[
            AgentSkill(
                id="purchase_bandwidth",
                name="Purchase Bandwidth",
                description=(
                    "Given a tier or bandwidth requirement, negotiates with a "
                    "provider, settles on chain, and activates the service."
                ),
                tags=["bandwidth", "agent2agent"],
                examples=["I need 5 Mbps for 10 minutes."],
            ),
        ],
    )

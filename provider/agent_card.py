"""Builds the a2a.types.AgentCard for the bandwidth provider agent."""
from __future__ import annotations

from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
)

from shared.config import Config


def build_provider_agent_card(cfg: Config) -> AgentCard:
    """Build the provider's A2A AgentCard using `cfg.provider_base_url`."""
    a2a_url = f"{cfg.provider_base_url}/a2a"
    return AgentCard(
        name="Bandwidth Provider Agent",
        description=("Sells time-bound bandwidth packages via atomic on-chain "
                     "escrow + ERC-721 credential. Activates SDN policy "
                     "(gNMI policer + tc rate-limit) on credential presentation."),
        version="2.0.0",
        default_input_modes=["application/json", "text/plain"],
        default_output_modes=["application/json"],
        capabilities=AgentCapabilities(streaming=False, extended_agent_card=False),
        supported_interfaces=[AgentInterface(protocol_binding="JSONRPC",
                                             url=a2a_url)],
        skills=[
            AgentSkill(id="get_catalog", name="Get Catalog",
                       description="Returns available bandwidth tiers.",
                       tags=["bandwidth", "catalog"],
                       examples=['{"action": "get_catalog"}']),
            AgentSkill(id="request_quote", name="Request Quote",
                       description=("Issues an agreementId-bound price quote "
                                    "for a chosen tier."),
                       tags=["bandwidth", "quote", "escrow"],
                       examples=['{"action": "request_quote", '
                                 '"package_id": "medium", "consumer_address": "0x..."}']),
            AgentSkill(id="activate", name="Activate Service",
                       description=("Verifies NFT credential ownership and "
                                    "triggers SDN allocation."),
                       tags=["bandwidth", "activation", "sdn"],
                       examples=['{"action": "activate", "token_id": 7, '
                                 '"nonce": "1730000000", "signature": "0x..."}']),
        ],
    )

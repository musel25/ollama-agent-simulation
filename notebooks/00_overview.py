import marimo

__generated_with = "0.23.8"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # 00 — Overview

    The full system in one page. **Read this first.**

    Two agents (consumer, provider) negotiate a time-bound bandwidth lease, settle it on Ethereum via an atomic on-chain swap (ETH ↔ ERC-721 credential), and the provider activates SDN policy bound to that credential. This series unpacks every layer.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## The 6-stage flow

    1. **Discover** — consumer fetches the provider's AgentCard.
    2. **Browse + Quote** — consumer asks for the catalog and a price quote.
    3. **Lock payment** — consumer calls `escrow.requestAgreement{value: priceWei}`.
    4. **Mint + swap** — provider mints an NFT, calls `escrow.deposit`; the contract atomically transfers NFT→consumer and ETH→provider.
    5. **Present credential** — consumer signs a fresh nonce, provider verifies on-chain ownership.
    6. **Activate SDN** — provider pushes a gNMI policer + tc rate-limit to the PE/CE bound to the NFT's `endpoint`.
    """)
    return


@app.cell
def _():
    import sys, pathlib
    _ROOT = pathlib.Path(__file__).resolve().parent.parent
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))

    from notebooks._viz import render_mermaid

    return (render_mermaid,)


@app.cell
def _(render_mermaid):
    render_mermaid("""
    sequenceDiagram
      participant C as Consumer
      participant P as Provider
      participant E as Escrow
      participant N as NFT
      participant S as SDN
      C->>P: discover (AgentCard)
      C->>P: browse + request_quote
      C->>E: requestAgreement{value}
      E-->>P: AgreementRequested event
      P->>N: mint(agreement, mbps, duration, endpoint)
      P->>E: deposit(agreement, tokenId)
      E->>N: transfer NFT to consumer
      E->>P: pay ETH
      C->>P: present_credential (signed nonce)
      P->>N: ownerOf(tokenId) check
      P->>S: allocate_bandwidth (gNMI + tc)
      P-->>C: status=active, endpoint
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Where to go next

    | Layer | Start here |
    |---|---|
    | Smart contracts | [01a_chain_contract_model](01a_chain_contract_model.py) |
    | MCP (tool protocol) | [02a_mcp_concepts](02a_mcp_concepts.py) |
    | A2A (agent protocol) | [03a_a2a_concepts](03a_a2a_concepts.py) |
    | Consumer LangGraph | [04a_graph_state_schema](04a_graph_state_schema.py) |
    | Provider inventory | [05a_inventory_and_expiry](05a_inventory_and_expiry.py) |
    | Full negotiation | [06_end_to_end](06_end_to_end.py) |
    | Network / SDN | [07a_network_concepts](07a_network_concepts.py) |
    """)
    return


if __name__ == "__main__":
    app.run()

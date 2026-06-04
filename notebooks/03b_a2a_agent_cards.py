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
    # 03b — Agent cards

    The discovery payload, rendered.

    When two agents meet over A2A, the first thing one does is fetch the other's `/.well-known/agent-card.json`. Below: both cards from this repo, rendered.
    """)
    return


@app.cell
def _():
    import sys, pathlib
    _ROOT = pathlib.Path(__file__).resolve().parent.parent
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))

    from notebooks._viz import render_agent_card
    from shared.config import Config

    PROVIDER = '0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d'
    CONSUMER = '0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a'
    return CONSUMER, Config, PROVIDER, render_agent_card


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Provider card
    """)
    return


@app.cell
def _(Config, PROVIDER, render_agent_card):
    from provider.agent_card import build_provider_agent_card
    from google.protobuf.json_format import MessageToDict
    cfg_p = Config(provider_private_key=PROVIDER, sdn_mock=True)
    card_p = build_provider_agent_card(cfg_p)
    card_p_dict = MessageToDict(card_p, preserving_proto_field_name=True)
    render_agent_card(card_p_dict)
    return MessageToDict, card_p_dict


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Consumer card
    """)
    return


@app.cell
def _(CONSUMER, Config, MessageToDict, render_agent_card):
    from consumer.agent_card import build_consumer_agent_card
    cfg_c = Config(consumer_private_key=CONSUMER)
    card_c = build_consumer_agent_card(cfg_c)
    render_agent_card(MessageToDict(card_c, preserving_proto_field_name=True))
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Side-by-side observations

    - **Skills count.** Provider exposes 3 skills (`get_catalog`, `request_quote`, `activate`); consumer exposes 1 (`purchase_bandwidth`). Asymmetric: the provider is more "callable", the consumer is more "active" (it's the one driving the LangGraph).
    - **Interfaces.** Provider exposes JSONRPC at `/a2a` (a2a-sdk's standard binding). Consumer exposes plain HTTP at `/chat` because callers send a free-text user message, not a typed action.
    - **Modes.** Provider accepts both `application/json` and `text/plain`; consumer accepts `text/plain` (chat input) and emits both.
    - **Discovery.** Both cards live at `/.well-known/agent-card.json`. The consumer's `discover_provider` MCP tool checks that the card's `skills[*].id` set is a superset of `("get_catalog", "request_quote", "activate")` before deciding the provider is usable.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Raw card JSON
    """)
    return


@app.cell
def _(card_p_dict):
    import json
    print(json.dumps(card_p_dict, indent=2))
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Next: [03c — walkthrough](03c_a2a_walkthrough.py).
    """)
    return


if __name__ == "__main__":
    app.run()

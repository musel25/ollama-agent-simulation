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
    # 04c — LLM prompts

    The consumer graph touches an LLM at exactly two nodes: `pick_tier_node` (decision) and `summary_node` (informational). Here we look at each prompt verbatim, plus how `pick_tier_node` recovers when the LLM disobeys.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Prompt A — `pick_tier_node`

    ```text
    User says: <user_message>
    Catalog tiers (smallest to largest):
    - small: 2 Mbps
    - medium: 5 Mbps
    - large: 8 Mbps

    Reply with EXACTLY ONE WORD: the packageId you choose.
    No punctuation, no explanation, no JSON. Just the word.
    ```

    The prompt is built in `consumer/graph.py:154-160`. Why one word?

    - **Cheap to parse.** A regex pulls `[a-zA-Z]+` tokens and checks each against the valid tier set.
    - **Cheap to fall back.** If no valid token matches, `deterministic_tier_pick` (in `consumer/tier_selection.py`) takes over with rule-based logic: "X Mbps" → smallest tier with `mbps >= X`; tier word match (`cheapest` → smallest); else middle tier.
    - **Resilient to chatty models.** Even verbose LLMs that ignore "no explanation" usually mention the tier word somewhere; the regex still finds it.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Three example LLM outputs, three parses
    """)
    return


@app.cell
def _():
    import sys, pathlib
    _ROOT = pathlib.Path(__file__).resolve().parent.parent
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    return


@app.cell
def _():
    import re
    def parse_pick(raw, valid):
        for token in re.findall(r"[a-zA-Z]+", raw.lower()):
            if token in valid:
                return token
        return None
    valid = {"small", "medium", "large"}
    for raw in ["medium", "I would say MEDIUM is best", "42"]:
        print(repr(raw), "→", parse_pick(raw, valid) or "DETERMINISTIC FALLBACK")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Deterministic fallback semantics
    """)
    return


@app.cell
def _():
    from consumer.tier_selection import deterministic_tier_pick
    catalog = [
        {"packageId": "small",  "mbps": 2, "durationSeconds": 600, "priceWei": 10**16},
        {"packageId": "medium", "mbps": 5, "durationSeconds": 600, "priceWei": 2*10**16},
        {"packageId": "large",  "mbps": 8, "durationSeconds": 600, "priceWei": 8*10**16},
    ]
    print('"I need 5 Mbps" →', deterministic_tier_pick("I need 5 Mbps", catalog)["packageId"])
    print('"cheapest please" →', deterministic_tier_pick("cheapest please", catalog)["packageId"])
    print('"asdf" →', deterministic_tier_pick("asdf", catalog)["packageId"])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Prompt B — `summary_node`

    ```text
    Briefly acknowledge a successful bandwidth purchase:
    - tier: <chosen_tier>
    - bandwidth: <chosen_mbps> Mbps
    - agreementId: <agreement_id>
    - tokenId: <token_id>
    Reply with one short sentence.
    ```

    Built in `consumer/graph.py:303-310`. Notable: even though we call the LLM, we DON'T use its response as `final_response`. The actual returned text is template-built:

    ```python
    sentence = (f"Active service — {state['chosen_tier']} tier "
                f"({state['chosen_mbps']} Mbps), "
                f"agreementId={state['agreement_id']}, "
                f"tokenId={state['token_id']}.")
    ```

    The LLM call is decorative — it goes into `state["thinking"]` for observability and demonstrates that LangGraph supports both LLM-driven and template-driven nodes. In production, removing the LLM call here would change nothing externally observable.

    Next: [04d — graph walkthrough](04d_graph_walkthrough.py).
    """)
    return


if __name__ == "__main__":
    app.run()

"""Smoke test for notebooks/_viz.py renderers.

We do not assert on rendered HTML/PNG content — just that every helper
returns the expected IPython.display type without raising.
"""
from __future__ import annotations

import pytest
from IPython.display import HTML, Image


def test_viz_module_imports():
    from notebooks import _viz
    expected = {
        "render_mermaid", "render_agent_card", "render_mcp_tools",
        "render_state", "render_chat_log", "render_chain_status",
        "render_event_timeline", "render_topology", "toggle_before_after",
    }
    missing = expected - set(dir(_viz))
    assert not missing, f"missing helpers: {missing}"


def test_render_mermaid_returns_image_or_html():
    from notebooks._viz import render_mermaid
    out = render_mermaid("graph LR; A-->B")
    assert isinstance(out, (Image, HTML))


def test_render_agent_card_returns_html():
    from notebooks._viz import render_agent_card
    card = {
        "name": "X", "version": "1.0", "description": "d",
        "capabilities": {"streaming": False},
        "supported_interfaces": [{"protocol_binding": "JSONRPC", "url": "/a2a"}],
        "skills": [{"id": "s", "name": "S", "description": "ds", "tags": []}],
    }
    out = render_agent_card(card)
    assert isinstance(out, HTML)
    assert "X" in out.data


def test_render_state_returns_html_with_diff():
    from notebooks._viz import render_state
    prev = {"a": 1, "b": 2}
    cur = {"a": 1, "b": 3, "c": 4}
    out = render_state(cur, prev)
    assert isinstance(out, HTML)
    # added + changed keys are surfaced
    assert "c" in out.data
    assert "b" in out.data


def test_render_chat_log_returns_html():
    from notebooks._viz import render_chat_log
    log = [{"from": "consumer", "message": "hi"},
           {"from": "provider", "message": "hello"}]
    out = render_chat_log(log)
    assert isinstance(out, HTML)
    assert "hi" in out.data and "hello" in out.data


def test_render_chain_status_handles_status_dict():
    from notebooks._viz import render_chain_status_from_dict
    ag = {"consumer": "0xC", "provider": "0xP", "bandwidthMbps": 5,
          "durationSeconds": 600, "priceWei": 10**16, "tokenId": 0,
          "status": "REQUESTED"}
    out = render_chain_status_from_dict(123, ag)
    assert isinstance(out, HTML)
    assert "REQUESTED" in out.data


def test_render_event_timeline_returns_html():
    from notebooks._viz import render_event_timeline
    events = [{"event": "AgreementRequested", "block": 1, "args": {"id": 1},
               "txHash": "0xabc", "gas": 90000}]
    out = render_event_timeline(events)
    assert isinstance(out, HTML)
    assert "AgreementRequested" in out.data


def test_render_topology_returns_image_or_html():
    from notebooks._viz import render_topology_from_rows
    rows = [
        {"tier": "small", "mbps": 2, "slots": [
            {"pe": "pe1", "subinterface": "ethernet-1/2.0",
             "ce": "ce1", "agreementId": None}]},
    ]
    out = render_topology_from_rows(rows, active_agreement_ids=set(),
                                    ce_peer={"ce1": "ce2"})
    assert isinstance(out, (Image, HTML))


def test_toggle_before_after_returns_widget_or_html():
    from notebooks._viz import toggle_before_after
    a = HTML("<div>A</div>")
    b = HTML("<div>B</div>")
    out = toggle_before_after(a, b)
    # ipywidgets.VBox or HTML fallback
    assert out is not None

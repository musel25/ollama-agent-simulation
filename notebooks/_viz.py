"""Notebook rendering helpers.

Single source of truth for mermaid diagrams, MCP-tool inspectors,
A2A agent-card views, JSON state diffs, chat-bubble logs, on-chain
state pills, event timelines, network-topology graphs, and the
before/after ipywidgets toggle. Imported by every notebook in the
pedagogical series.

Mermaid rendering uses the mermaid.ink HTTP service (the same approach
LangGraph uses internally for draw_mermaid_png). Offline behavior:
fall back to a fenced markdown block so notebooks remain readable.
"""
from __future__ import annotations

import base64
import html as _html
import io
import json
from typing import Any, Iterable

import httpx
from IPython.display import HTML, Image


def render_mermaid(source: str) -> HTML | Image:
    """Render mermaid source as a PNG via mermaid.ink, or fenced text on failure."""
    try:
        encoded = base64.urlsafe_b64encode(source.encode("utf-8")).decode("ascii")
        url = f"https://mermaid.ink/img/{encoded}"
        resp = httpx.get(url, timeout=10.0)
        resp.raise_for_status()
        return Image(data=resp.content, format="png")
    except Exception:
        # offline or rate-limited fallback
        escaped = _html.escape(source)
        return HTML(f"<pre style='background:#f6f8fa;padding:8px;"
                    f"border-radius:6px'><code>{escaped}</code></pre>")


def render_agent_card(card: dict) -> HTML:
    """Render an a2a-sdk AgentCard (as dict) as a styled HTML card.

    `card` is the result of MessageToDict(agent_card, preserving_proto_field_name=True)
    or the JSON returned by /.well-known/agent-card.json.
    """
    name = _html.escape(str(card.get("name", "?")))
    version = _html.escape(str(card.get("version", "?")))
    desc = _html.escape(str(card.get("description", "")))
    caps = card.get("capabilities", {}) or {}
    caps_html = " ".join(
        f"<span style='background:#eef;padding:2px 8px;border-radius:10px;"
        f"margin-right:4px;font-size:12px'>{_html.escape(k)}: "
        f"{_html.escape(str(v))}</span>"
        for k, v in caps.items()
    )
    interfaces_rows = "".join(
        f"<tr><td>{_html.escape(str(i.get('protocol_binding', '?')))}</td>"
        f"<td><code>{_html.escape(str(i.get('url', '?')))}</code></td></tr>"
        for i in (card.get("supported_interfaces") or [])
    )
    skills = card.get("skills") or []
    skills_html = "".join(
        f"<li><b>{_html.escape(s.get('id', ''))}</b> — "
        f"{_html.escape(s.get('name', ''))}: "
        f"{_html.escape(s.get('description', ''))} "
        f"<span style='color:#888;font-size:12px'>"
        f"[{', '.join(_html.escape(t) for t in s.get('tags') or [])}]</span></li>"
        for s in skills
    )
    body = (
        f"<div style='border:1px solid #ddd;border-radius:8px;padding:16px;"
        f"max-width:760px;font-family:system-ui'>"
        f"<div style='font-size:18px;font-weight:600'>{name} "
        f"<span style='color:#888;font-size:13px'>v{version}</span></div>"
        f"<div style='color:#444;margin:6px 0'>{desc}</div>"
        f"<div style='margin:8px 0'>{caps_html}</div>"
        f"<table style='border-collapse:collapse;font-size:13px'>"
        f"<thead><tr><th align='left'>binding</th><th align='left'>url</th></tr></thead>"
        f"<tbody>{interfaces_rows}</tbody></table>"
        f"<div style='margin-top:10px;font-weight:600'>Skills</div>"
        f"<ul style='font-size:13px'>{skills_html}</ul>"
        f"</div>"
    )
    return HTML(body)


def render_mcp_tools(mcp) -> HTML:
    """Render every tool registered on a FastMCP server as an HTML card grid.

    Reads `mcp._local_provider._components` (FastMCP internals) and renders
    name + description + JSON Schema (input/output) for each tool.
    """
    components = getattr(getattr(mcp, "_local_provider", None),
                         "_components", {}) or {}
    tools = [v for k, v in components.items() if k.startswith("tool:")]

    cards: list[str] = []
    for t in tools:
        name = _html.escape(getattr(t, "name", "?"))
        desc = _html.escape(getattr(t, "description", "") or "")
        schema = getattr(t, "input_schema", None) or getattr(t, "schema", None)
        try:
            schema_json = json.dumps(schema, indent=2, default=str) if schema else "{}"
        except Exception:
            schema_json = str(schema)
        cards.append(
            f"<div style='border:1px solid #ddd;border-radius:8px;padding:12px;"
            f"margin:6px;flex:1 1 320px;max-width:380px'>"
            f"<div style='font-weight:600;font-family:monospace'>{name}</div>"
            f"<div style='color:#555;font-size:13px;margin:4px 0'>{desc}</div>"
            f"<details><summary style='cursor:pointer;font-size:12px;color:#06c'>"
            f"input schema</summary>"
            f"<pre style='background:#f6f8fa;padding:8px;border-radius:4px;"
            f"font-size:12px;overflow-x:auto'>"
            f"{_html.escape(schema_json)}</pre></details>"
            f"</div>"
        )
    grid = (
        f"<div style='display:flex;flex-wrap:wrap'>"
        f"{''.join(cards)}"
        f"</div>"
    )
    header = (
        f"<div style='font-family:system-ui'>"
        f"<div style='font-weight:600;margin-bottom:6px'>"
        f"FastMCP server: {_html.escape(getattr(mcp, 'name', '?'))} "
        f"<span style='color:#888;font-size:12px'>"
        f"({len(tools)} tools)</span></div>"
        f"{grid}</div>"
    )
    return HTML(header)


def render_state(state: dict, prev: dict | None = None) -> HTML:
    """Pretty-print state as JSON; if prev given, highlight added/changed keys."""
    keys = sorted(set(state) | set(prev or {}))
    rows: list[str] = []
    for k in keys:
        new_val = state.get(k, "<missing>")
        old_val = (prev or {}).get(k, "<absent>")
        try:
            new_json = json.dumps(new_val, default=str)
        except Exception:
            new_json = str(new_val)
        if prev is None:
            color, label = "#000", ""
        elif k not in prev:
            color, label = "#0a0", " ＋"
        elif k not in state:
            color, label = "#a00", " −"
        elif new_val != old_val:
            color, label = "#a60", " Δ"
        else:
            color, label = "#666", ""
        rows.append(
            f"<tr><td style='color:{color};font-family:monospace;"
            f"vertical-align:top'>{_html.escape(k)}{label}</td>"
            f"<td style='font-family:monospace;font-size:12px'>"
            f"{_html.escape(new_json[:300])}"
            f"{'…' if len(new_json) > 300 else ''}</td></tr>"
        )
    return HTML(
        f"<table style='border-collapse:collapse;font-size:13px'>"
        f"<thead><tr><th align='left'>key</th><th align='left'>value</th></tr>"
        f"</thead><tbody>{''.join(rows)}</tbody></table>"
    )


_BUBBLE_COLORS = {
    "consumer": ("#e3f2fd", "#0d47a1"),  # blue
    "provider": ("#e8f5e9", "#1b5e20"),  # green
    "system":   ("#fff3e0", "#e65100"),  # orange
}


def render_chat_log(log: Iterable[dict]) -> HTML:
    """Render an inter-agent log as chat bubbles, color-coded by sender."""
    bubbles: list[str] = []
    for entry in log:
        sender = (entry.get("from") or "").lower()
        bg, fg = _BUBBLE_COLORS.get(sender, ("#f0f0f0", "#222"))
        align = "flex-start" if sender == "consumer" else "flex-end"
        text = _html.escape(str(entry.get("message", "")))
        bubbles.append(
            f"<div style='display:flex;justify-content:{align};margin:4px 0'>"
            f"<div style='background:{bg};color:{fg};padding:6px 10px;"
            f"border-radius:12px;max-width:70%;font-family:system-ui;font-size:13px'>"
            f"<div style='font-size:10px;opacity:0.7;text-transform:uppercase'>"
            f"{_html.escape(sender)}</div>{text}</div></div>"
        )
    return HTML(
        f"<div style='font-family:system-ui;max-width:760px'>"
        f"{''.join(bubbles)}</div>"
    )


_STATUS_PILL = {
    "NONE":      ("#eee", "#555"),
    "REQUESTED": ("#fff3cd", "#856404"),
    "ACTIVE":    ("#d4edda", "#155724"),
    "CLOSED":    ("#cce5ff", "#004085"),
    "CANCELLED": ("#f8d7da", "#721c24"),
}


def _agreement_table(agreement_id: int, ag: dict) -> str:
    rows: list[str] = []
    for k in ("consumer", "provider", "bandwidthMbps", "durationSeconds",
              "priceWei", "requestDeadline", "tokenId", "status"):
        if k not in ag:
            continue
        v = ag[k]
        rows.append(
            f"<tr><td style='font-family:monospace;color:#555'>{k}</td>"
            f"<td style='font-family:monospace'>{_html.escape(str(v))}</td></tr>"
        )
    status = str(ag.get("status", "NONE"))
    bg, fg = _STATUS_PILL.get(status, ("#eee", "#555"))
    pill = (
        f"<span style='background:{bg};color:{fg};padding:3px 10px;"
        f"border-radius:12px;font-weight:600;font-size:12px'>{status}</span>"
    )
    return (
        f"<div style='font-family:system-ui;max-width:560px'>"
        f"<div style='font-weight:600;margin-bottom:4px'>"
        f"Agreement #{agreement_id} {pill}</div>"
        f"<table style='border-collapse:collapse;font-size:13px'>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


def render_chain_status_from_dict(agreement_id: int, ag: dict) -> HTML:
    """Render an Agreement struct (already a dict) with its colored status pill."""
    return HTML(_agreement_table(agreement_id, ag))


def render_chain_status(escrow, agreement_id: int) -> HTML:
    """Render an Agreement looked up live from a web3 contract handle."""
    raw = escrow.functions.getAgreement(int(agreement_id)).call()
    # tuple order matches BandwidthEscrow.Agreement struct
    ag = {
        "consumer": raw[0], "provider": raw[1],
        "bandwidthMbps": int(raw[2]), "durationSeconds": int(raw[3]),
        "priceWei": int(raw[4]), "requestDeadline": int(raw[5]),
        "tokenId": int(raw[6]),
        "status": ("NONE", "REQUESTED", "ACTIVE", "CLOSED", "CANCELLED")[int(raw[7])],
    }
    return render_chain_status_from_dict(agreement_id, ag)


def render_event_timeline(events: Iterable[dict]) -> HTML:
    """Render a list of decoded chain events as a sortable HTML table."""
    rows: list[str] = []
    for e in events:
        args = e.get("args") or {}
        try:
            args_json = json.dumps(args, default=str)
        except Exception:
            args_json = str(args)
        rows.append(
            f"<tr>"
            f"<td>{int(e.get('block', 0))}</td>"
            f"<td><code>{_html.escape(str(e.get('event', '?')))}</code></td>"
            f"<td style='font-family:monospace;font-size:12px'>"
            f"{_html.escape(args_json[:240])}"
            f"{'…' if len(args_json) > 240 else ''}</td>"
            f"<td>{int(e.get('gas', 0)):,}</td>"
            f"<td><code style='font-size:11px'>"
            f"{_html.escape(str(e.get('txHash', ''))[:16])}…</code></td>"
            f"</tr>"
        )
    return HTML(
        f"<table style='border-collapse:collapse;font-size:13px;font-family:system-ui'>"
        f"<thead style='background:#f6f8fa'>"
        f"<tr><th>block</th><th>event</th><th>args</th>"
        f"<th>gas</th><th>tx</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _topology_mermaid(rows: list[dict],
                      active_agreement_ids: set[int],
                      ce_peer: dict) -> str:
    """Build a mermaid graph LR from a list of slot-pool rows."""
    pes: set[str] = set()
    ces: set[str] = set()
    edges: list[str] = []
    active_edges: list[str] = []
    for row in rows:
        for s in row.get("slots", []):
            pe, ce, sif = s["pe"], s["ce"], s["subinterface"]
            pes.add(pe); ces.add(ce)
            label = f"{row['mbps']} Mbps<br/>{sif}"
            edge = f"  {ce} ---|{label}| {pe}"
            if s.get("agreementId") in active_agreement_ids:
                active_edges.append(f"  linkStyle {len(edges)} stroke:#1b5e20,stroke-width:3px")
            edges.append(edge)
    nodes = "\n".join(
        [f"  {p}([PE: {p}])" for p in sorted(pes)]
        + [f"  {c}((CE: {c}))" for c in sorted(ces)]
    )
    pairs = "\n".join(
        f"  {a} -.peer.- {b}" for a, b in sorted(set(
            tuple(sorted([k, v])) for k, v in ce_peer.items() if k in ces and v in ces
        ))
    )
    return (
        "graph LR\n"
        f"{nodes}\n"
        f"{chr(10).join(edges)}\n"
        f"{pairs}\n"
        f"{chr(10).join(active_edges)}"
    )


def render_topology_from_rows(rows: list[dict],
                              active_agreement_ids: set[int],
                              ce_peer: dict) -> HTML | Image:
    """Render the network topology described by raw inventory rows."""
    return render_mermaid(_topology_mermaid(rows, active_agreement_ids, ce_peer))


def render_topology(slot_pool, active_agreement_ids: set[int],
                    ce_peer: dict) -> HTML | Image:
    """Render topology by reading rows directly off a SlotPool instance."""
    rows = slot_pool._read_and_reclaim()  # noqa: SLF001 — public read access
    return render_topology_from_rows(rows, active_agreement_ids, ce_peer)

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

"""
Thin wrapper around a2a-sdk's client primitives. Used by consumer MCP
tools that need to talk to a remote provider over A2A.

Design choice: open a fresh client per call. The cost is one resolve +
one HTTP round trip; we do not optimize for high call rates.

a2a-sdk 1.0.x uses google.protobuf classes, so:
  - construct Message/Part/SendMessageRequest with snake_case kwargs
  - wrap dict payloads as google.protobuf.Value(struct_value=Struct(...))
  - StreamResponse is a oneof — read .artifact_update.artifact for results
"""
from __future__ import annotations

import secrets

import httpx
from a2a.client import ClientConfig, create_client
from a2a.types import Message, Part, Role, SendMessageRequest
from google.protobuf.json_format import MessageToDict, ParseDict
from google.protobuf.struct_pb2 import Struct, Value


def _dict_to_value(d: dict) -> Value:
    s = Struct()
    ParseDict(d, s)
    return Value(struct_value=s)


def _short_id() -> str:
    return secrets.token_hex(8)


async def fetch_agent_card(provider_url: str) -> dict:
    """Fetch /.well-known/agent-card.json from *provider_url* (used for discovery)."""
    async with httpx.AsyncClient(timeout=10.0) as http:
        resp = await http.get(f"{provider_url.rstrip('/')}/.well-known/agent-card.json")
        resp.raise_for_status()
        return resp.json()


async def send_provider_action(provider_url: str, payload: dict) -> dict:
    """
    Send a single A2A message to *provider_url* with parts[0].data = payload,
    return the first artifact's data part as a dict.

    *provider_url* is the agent base URL (e.g. http://prov:8002). The card
    resolver fetches /.well-known/agent-card.json from it.
    """
    async with httpx.AsyncClient(timeout=60.0) as http:
        config = ClientConfig(streaming=False, httpx_client=http)
        client = await create_client(agent=provider_url, client_config=config)

        msg = Message(
            message_id=_short_id(),
            role=Role.ROLE_USER,
            parts=[Part(data=_dict_to_value(payload), media_type="application/json")],
        )
        request = SendMessageRequest(message=msg)

        async for chunk in client.send_message(request):
            artifacts = []
            which = chunk.WhichOneof("payload") if hasattr(chunk, "WhichOneof") else None
            if which == "artifact_update":
                au = chunk.artifact_update
                if au.artifact is not None:
                    artifacts.append(au.artifact)
            elif which == "task":
                task = chunk.task
                artifacts.extend(getattr(task, "artifacts", []) or [])
            else:
                au = getattr(chunk, "artifact_update", None)
                if au is not None and getattr(au, "artifact", None) is not None:
                    artifacts.append(au.artifact)
                task = getattr(chunk, "task", None)
                if task is not None:
                    artifacts.extend(getattr(task, "artifacts", []) or [])

            for artifact in artifacts:
                for part in artifact.parts:
                    data = getattr(part, "data", None)
                    if data is not None:
                        return MessageToDict(data, preserving_proto_field_name=True)
        raise RuntimeError("provider returned no artifacts")

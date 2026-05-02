"""
BandwidthProviderExecutor — bridges A2A messages to the provider's MCP tools.

Inbound: A2A Message with a single `data` Part containing {"action": ...}.
Routes:
  - "get_catalog"      → MCP get_catalog
  - "request_quote"    → MCP request_quote
  - "activate"         → MCP verify_credential_ownership + allocate_bandwidth

Outbound: TaskArtifactUpdateEvent carrying a `data` Part with the JSON response,
followed by a TaskStatusUpdateEvent with TASK_STATE_COMPLETED.

Notes on a2a-sdk shape: it generates protobuf classes from a2a.proto, so:
  - Part.data is a google.protobuf.Value (use MessageToDict/ParseDict to convert).
  - Constructors are kwargs that match proto field names.
  - TaskState is an int-valued enum.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import (
    Artifact,
    Part,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
)
from fastmcp import Client as MCPClient
from google.protobuf.json_format import MessageToDict, ParseDict
from google.protobuf.struct_pb2 import Struct, Value

from provider.catalog import slot_pool
from provider.mcp_server import mcp
from shared.a2a_messages import (
    ActivateRequest,
    BrowseCatalogRequest,
    ErrorResponse,
    QuoteRequest,
)

log = logging.getLogger("provider.executor")


def _value_to_dict(v: Any) -> dict | None:
    """Convert a google.protobuf.Value (or a plain dict) to a python dict."""
    if v is None:
        return None
    if isinstance(v, dict):
        return dict(v)
    try:
        return MessageToDict(v, preserving_proto_field_name=True)
    except Exception:
        return None


def _dict_to_value(d: dict) -> Value:
    s = Struct()
    ParseDict(d, s)
    return Value(struct_value=s)


def _make_data_part(data: dict) -> Part:
    return Part(data=_dict_to_value(data), media_type="application/json")


class BandwidthProviderExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        data = self._extract_data_part(context)
        if data is None:
            await self._emit_error(event_queue, context.task_id,
                                   "expected message with a single data part")
            return

        action = data.get("action")
        try:
            if action == "get_catalog":
                BrowseCatalogRequest.model_validate(data)
                await self._handle_catalog(event_queue, context.task_id)
            elif action == "request_quote":
                req = QuoteRequest.model_validate(data)
                await self._handle_quote(event_queue, context.task_id, req)
            elif action == "activate":
                req = ActivateRequest.model_validate(data)
                await self._handle_activate(event_queue, context.task_id, req)
            else:
                await self._emit_error(event_queue, context.task_id,
                                       f"unknown action: {action!r}")
        except Exception as e:
            log.exception("Executor error")
            await self._emit_error(event_queue, context.task_id, str(e))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=context.task_id,
                status=TaskStatus(state=TaskState.TASK_STATE_CANCELED),
            )
        )

    async def _handle_catalog(self, queue: EventQueue, task_id: str) -> None:
        async with MCPClient(mcp) as client:
            result = await client.call_tool("get_catalog", {})
            payload = json.loads(result.content[0].text)
        await self._emit_data(queue, task_id, {"catalog": payload})

    async def _handle_quote(self, queue: EventQueue, task_id: str, req: QuoteRequest) -> None:
        async with MCPClient(mcp) as client:
            result = await client.call_tool("request_quote", {
                "package_id": req.package_id,
                "consumer_address": req.consumer_address,
            })
            data = json.loads(result.content[0].text)
        if "error" in data:
            await self._emit_data(queue, task_id, {"error": data["error"]})
            return
        await self._emit_data(queue, task_id, {
            "agreementId": str(data["agreementId"]),
            "priceWei": data["priceWei"],
            "bandwidthMbps": data["bandwidthMbps"],
            "durationSeconds": data["durationSeconds"],
        })

    async def _handle_activate(self, queue: EventQueue, task_id: str, req: ActivateRequest) -> None:
        async with MCPClient(mcp) as client:
            verify = await client.call_tool(
                "verify_credential_ownership",
                {"token_id": req.token_id, "signature": req.signature, "nonce": req.nonce},
            )
            v = json.loads(verify.content[0].text)
            if not v.get("ok"):
                await self._emit_data(queue, task_id, {
                    "status": "denied",
                    "reason": v.get("reason", "verification failed"),
                })
                return

            slot = slot_pool.lookup(int(v["agreement_id"]))
            if slot is None:
                await self._emit_data(queue, task_id, {
                    "status": "denied",
                    "reason": f"no slot bound to agreement {v['agreement_id']}",
                })
                return

            alloc = await client.call_tool(
                "allocate_bandwidth",
                {
                    "customer_id": v["signer"],
                    "pe": slot.pe,
                    "subinterface": slot.subinterface,
                    "mbps": float(v["mbps"]),
                },
            )
            alloc_data = json.loads(alloc.content[0].text)

        await self._emit_data(queue, task_id, {
            "status": "active",
            "bandwidth_mbps": int(v["mbps"]),
            "seconds_remaining": int(v.get("seconds_remaining", 0)),
            "endpoint": v.get("endpoint", ""),
            "allocation": alloc_data,
        })

    @staticmethod
    def _extract_data_part(context: RequestContext) -> dict | None:
        msg = context.message
        if msg is None:
            return None
        parts = getattr(msg, "parts", None) or []
        for part in parts:
            d = getattr(part, "data", None)
            if d is None:
                continue
            converted = _value_to_dict(d)
            if converted:
                return converted
        return None

    async def _emit_data(self, queue: EventQueue, task_id: str, data: dict) -> None:
        await queue.enqueue_event(
            TaskArtifactUpdateEvent(
                task_id=task_id,
                artifact=Artifact(
                    artifact_id="result",
                    parts=[_make_data_part(data)],
                ),
            )
        )
        await queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=task_id,
                status=TaskStatus(state=TaskState.TASK_STATE_COMPLETED),
            )
        )

    async def _emit_error(self, queue: EventQueue, task_id: str, message: str) -> None:
        await queue.enqueue_event(
            TaskArtifactUpdateEvent(
                task_id=task_id,
                artifact=Artifact(
                    artifact_id="error",
                    parts=[_make_data_part(ErrorResponse(error=message).model_dump())],
                ),
            )
        )
        await queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=task_id,
                status=TaskStatus(state=TaskState.TASK_STATE_FAILED),
            )
        )

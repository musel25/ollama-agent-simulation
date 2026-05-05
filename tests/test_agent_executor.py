"""
Unit tests for BandwidthProviderExecutor.

Drives the executor directly with a fake EventQueue, no Starlette involved.
Inputs use real proto Value-wrapped Part data so the executor's value→dict
helper is exercised end-to-end.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from a2a.types import Message, Part
from google.protobuf.json_format import MessageToDict, ParseDict
from google.protobuf.struct_pb2 import Struct, Value

from provider.agent_executor import BandwidthProviderExecutor


class FakeQueue:
    def __init__(self):
        self.events = []

    async def enqueue_event(self, event):
        self.events.append(event)


def _data_part(d: dict) -> Part:
    s = Struct()
    ParseDict(d, s)
    return Part(data=Value(struct_value=s), media_type="application/json")


def _make_context(data: dict) -> MagicMock:
    msg = Message(message_id="m1", parts=[_data_part(data)])
    ctx = MagicMock()
    ctx.message = msg
    ctx.task_id = "task-1"
    ctx.context_id = "ctx-1"  # protobuf rejects MagicMock here
    return ctx


def _artifact_payload(event) -> dict:
    """Extract the dict payload from a TaskArtifactUpdateEvent's first data part."""
    part = event.artifact.parts[0]
    return MessageToDict(part.data, preserving_proto_field_name=True)


@pytest.mark.asyncio
async def test_executor_returns_catalog():
    ex = BandwidthProviderExecutor()
    queue = FakeQueue()
    ctx = _make_context({"action": "get_catalog"})

    await ex.execute(ctx, queue)

    assert len(queue.events) == 2
    payload = _artifact_payload(queue.events[0])
    assert "catalog" in payload
    assert len(payload["catalog"]) == 3


@pytest.mark.asyncio
async def test_executor_unknown_action_emits_error():
    ex = BandwidthProviderExecutor()
    queue = FakeQueue()
    ctx = _make_context({"action": "no_such_action"})

    await ex.execute(ctx, queue)

    assert len(queue.events) == 2
    payload = _artifact_payload(queue.events[0])
    assert "error" in payload


@pytest.mark.asyncio
async def test_executor_returns_quote():
    ex = BandwidthProviderExecutor()
    queue = FakeQueue()
    ctx = _make_context({
        "action": "request_quote",
        "package_id": "small",
        "consumer_address": "0x0000000000000000000000000000000000000001",
    })

    await ex.execute(ctx, queue)

    assert len(queue.events) == 2
    payload = _artifact_payload(queue.events[0])
    assert "agreementId" in payload
    assert payload["bandwidthMbps"] == 2

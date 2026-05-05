"""
Pydantic models for the structured `data` parts agents exchange over A2A.

The A2A `Message.parts[*].data` field is an arbitrary JSON object
(google.protobuf.Value/Struct on the wire). We constrain its shape with
these models so executors can parse safely.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel


class BrowseCatalogRequest(BaseModel):
    action: Literal["get_catalog"] = "get_catalog"


class QuoteRequest(BaseModel):
    action: Literal["request_quote"] = "request_quote"
    package_id: str
    consumer_address: str


class ActivateRequest(BaseModel):
    action: Literal["activate"] = "activate"
    token_id: int
    nonce: str
    signature: str


class CatalogEntry(BaseModel):
    packageId: str
    mbps: int
    durationSeconds: int
    priceWei: int
    availableSlots: int


class CatalogResponse(BaseModel):
    catalog: list[CatalogEntry]


class QuoteResponse(BaseModel):
    agreementId: str
    priceWei: int
    bandwidthMbps: int
    durationSeconds: int


class ActivateResponse(BaseModel):
    status: Literal["active", "denied"]
    bandwidth_mbps: Optional[int] = None
    seconds_remaining: Optional[int] = None
    endpoint: Optional[str] = None
    reason: Optional[str] = None


class ErrorResponse(BaseModel):
    error: str

"""
Shared code used by both consumer and provider.

This package holds cross-agent definitions that must stay in sync:
A2A message envelopes, Solidity ABIs, and the file-locked slot pool.

Key modules:
    a2a_messages   — Pydantic models for A2A request/response payloads
    contracts      — Web3 contract loaders and helpers
    slot_pool      — File-locked inventory used by the provider for slot allocation

ABIs are stored as JSON under shared/abi/.

See docs/04-architecture.md for the full picture.
"""

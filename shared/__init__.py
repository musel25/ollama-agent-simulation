"""
Shared code used by both consumer and provider.

Key modules:
    config         — Frozen Config dataclass with `from_env()` factory
    chain          — web3 helpers: send_tx, extract_token_id, STATUS_NAMES
    contracts      — Loads ABIs + deployment addresses; builds contract objects
    a2a_messages   — Pydantic models for A2A request/response payloads
    slot_pool      — File-locked (pe, subinterface, ce) reservations per tier
    anvil          — Context manager that spawns a local Anvil for notebooks/tests
    deploy         — Wrapper around `forge script` to deploy contracts in-process

ABIs are stored as JSON under shared/abi/.

See docs/03-architecture.md for the full picture.
"""

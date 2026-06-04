"""Headless execution of the offline marimo notebooks via ``marimo export script``.

The export resolves the reactive dataflow graph into a linear script and
executes it under the current Python interpreter. This catches:
  - syntax errors
  - import failures
  - undefined / duplicated variables across cells
  - cycles in the dependency graph
  - runtime errors in any cell that doesn't need external services

Skip notebooks that require external services:
  - 01c, 01d, 05a (anvil + forge)
  - 06 (anvil + ollama)

This test is opt-in via NOTEBOOK_SMOKE=1 because it can take ~30s.
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys

import pytest

OFFLINE_OK = [
    "00_overview.py",
    "01a_chain_contract_model.py",
    "01b_chain_escrow_lifecycle.py",
    "02a_mcp_concepts.py",
    "02b_mcp_tool_catalog.py",
    "02c_mcp_walkthrough.py",
    "03a_a2a_concepts.py",
    "03b_a2a_agent_cards.py",
    "03c_a2a_walkthrough.py",
    "04a_graph_state_schema.py",
    "04b_graph_topology.py",
    "04c_graph_llm_prompts.py",
    "04d_graph_walkthrough.py",
    "07a_network_concepts.py",
    "07b_network_topology.py",
    "07c_network_before_after.py",
    "07d_network_router_config.py",
]


@pytest.mark.skipif(
    os.environ.get("NOTEBOOK_SMOKE") != "1",
    reason="set NOTEBOOK_SMOKE=1 to run notebook execution smoke test",
)
@pytest.mark.parametrize("name", OFFLINE_OK)
def test_notebook_executes(name: str) -> None:
    nb_path = pathlib.Path("notebooks") / name
    assert nb_path.exists(), f"missing notebook: {nb_path}"
    # ``marimo export script`` topologically sorts cells and prints a runnable
    # script. Piping into the current interpreter executes it end-to-end.
    export = subprocess.run(
        [sys.executable, "-m", "marimo", "-q", "export", "script", str(nb_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [sys.executable, "-"],
        input=export.stdout,
        check=True,
        text=True,
        timeout=120,
    )

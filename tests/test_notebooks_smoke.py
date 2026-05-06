"""Headless execution of the offline notebooks via nbclient.

Skip notebooks that require external services:
  - 01c, 01d, 05a (anvil + forge)
  - 06 (anvil + ollama)

This test is opt-in via NOTEBOOK_SMOKE=1 because it can take ~30s.
"""
from __future__ import annotations

import os
import pathlib
import pytest
import nbformat
from nbclient import NotebookClient

OFFLINE_OK = [
    "00_overview.ipynb",
    "01a_chain_contract_model.ipynb",
    "01b_chain_escrow_lifecycle.ipynb",
    "02a_mcp_concepts.ipynb",
    "02b_mcp_tool_catalog.ipynb",
    "02c_mcp_walkthrough.ipynb",
    "03a_a2a_concepts.ipynb",
    "03b_a2a_agent_cards.ipynb",
    "03c_a2a_walkthrough.ipynb",
    "04a_graph_state_schema.ipynb",
    "04b_graph_topology.ipynb",
    "04c_graph_llm_prompts.ipynb",
    "04d_graph_walkthrough.ipynb",
    "07a_network_concepts.ipynb",
    "07b_network_topology.ipynb",
    "07c_network_before_after.ipynb",
    "07d_network_router_config.ipynb",
]


@pytest.mark.skipif(
    os.environ.get("NOTEBOOK_SMOKE") != "1",
    reason="set NOTEBOOK_SMOKE=1 to run notebook execution smoke test",
)
@pytest.mark.parametrize("name", OFFLINE_OK)
def test_notebook_executes(name):
    nb_path = pathlib.Path("notebooks") / name
    nb = nbformat.read(nb_path, as_version=4)
    NotebookClient(nb, timeout=120, kernel_name="python3").execute()

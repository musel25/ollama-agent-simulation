# Blockchain Primer

A hands-on, ground-up walkthrough of blockchain accounts, transactions, the EVM, and Solidity — driven by a local `anvil` chain through `cast` and `forge`. Ends with a guided read of `contracts/src/BandwidthEscrow.sol`.

Open **[`01a0_blockchain_primer.py`](01a0_blockchain_primer.py)** in marimo and run top to bottom:

```bash
uv run marimo edit notebooks/blockchain_primer/01a0_blockchain_primer.py
```

**Requirements:** Foundry (`anvil`, `cast`, `forge`) on `PATH`. Verify with `anvil --version`.

**Regenerating the notebook:** the notebook is assembled from `sections/*.py` by `build_notebook.py`. After editing any section module, run `uv run python notebooks/blockchain_primer/build_notebook.py`.

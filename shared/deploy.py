"""Deploy BandwidthEscrow + BandwidthNFT via `forge script`.

Exists so notebooks can deploy without dropping out to a Makefile or
shell. Requires the `forge` binary on PATH (install Foundry).

Side effect: `forge script ... --broadcast` writes
`contracts/deployments/local.json` which `shared/contracts.py` reads.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from eth_account import Account

from shared.config import Config


_REPO_ROOT = Path(__file__).resolve().parent.parent
_CONTRACTS_DIR = _REPO_ROOT / "contracts"
_DEPLOYMENTS_FILE = _CONTRACTS_DIR / "deployments" / "local.json"


def deploy_contracts(cfg: Config,
                     provider_address: str | None = None) -> dict[str, str]:
    """Run `forge script Deploy.s.sol`; return the deployed addresses.

    Raises if `cfg.deployer_private_key` is not set or `forge` is missing.
    """
    if not cfg.deployer_private_key:
        raise RuntimeError("Config.deployer_private_key is required")
    if provider_address is None:
        if cfg.provider_address:
            provider_address = cfg.provider_address
        elif cfg.provider_private_key:
            provider_address = Account.from_key(cfg.provider_private_key).address
        else:
            raise RuntimeError(
                "provider_address required (set Config.provider_private_key "
                "or Config.provider_address, or pass provider_address=...)")

    _DEPLOYMENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["forge", "script", "script/Deploy.s.sol",
         "--rpc-url", cfg.rpc_url,
         "--broadcast",
         "--private-key", cfg.deployer_private_key],
        cwd=_CONTRACTS_DIR,
        env={"DEPLOYER_PRIVATE_KEY": cfg.deployer_private_key,
             "PROVIDER_ADDRESS": provider_address,
             "PATH": __import__("os").environ.get("PATH", "")},
        check=True, capture_output=True,
    )
    return json.loads(_DEPLOYMENTS_FILE.read_text())

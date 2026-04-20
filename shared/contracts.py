import json
from pathlib import Path

from web3 import Web3

_ROOT = Path(__file__).parent.parent
_DEPLOYMENTS = _ROOT / "contracts" / "deployments" / "local.json"
_ABI_DIR = Path(__file__).parent / "abi"


def _load_deployments() -> dict:
    return json.loads(_DEPLOYMENTS.read_text())


def get_nft_contract(w3: Web3):
    addrs = _load_deployments()
    abi = json.loads((_ABI_DIR / "BandwidthNFT.json").read_text())
    return w3.eth.contract(address=Web3.to_checksum_address(addrs["bandwidthNFT"]), abi=abi)


def get_escrow_contract(w3: Web3):
    addrs = _load_deployments()
    abi = json.loads((_ABI_DIR / "BandwidthEscrow.json").read_text())
    return w3.eth.contract(address=Web3.to_checksum_address(addrs["bandwidthEscrow"]), abi=abi)

"""
Bandwidth service gateway — port 8003.
Verifies on-chain NFT ownership via signed timestamp nonce before serving metadata.
"""
import os
import time

import uvicorn
from eth_account import Account
from eth_account.messages import encode_defunct
from fastapi import FastAPI, Header, HTTPException, Query
from web3 import Web3

from shared.contracts import get_escrow_contract, get_nft_contract

RPC_URL = os.environ.get("RPC_URL", "http://localhost:8545")
w3 = Web3(Web3.HTTPProvider(RPC_URL))

app = FastAPI(title="Bandwidth Gateway")

NONCE_WINDOW = 300  # seconds; nonces older than this are rejected


@app.get("/service")
def check_service(
    token_id: int = Query(..., alias="tokenId"),
    x_signature: str = Header(..., alias="X-Signature"),
    x_nonce: str = Header(..., alias="X-Nonce"),
) -> dict:
    """
    Verify NFT ownership and return service status.

    Client sends:
      GET /service?tokenId=N
      X-Nonce: <unix_timestamp_string>
      X-Signature: <hex signature of the nonce>
    """
    # Validate nonce age
    try:
        nonce_time = int(x_nonce)
    except ValueError:
        raise HTTPException(400, "X-Nonce must be a unix timestamp integer string.")

    if abs(time.time() - nonce_time) > NONCE_WINDOW:
        raise HTTPException(401, "Nonce expired or too far in the future.")

    # Recover signer address from signature
    try:
        message = encode_defunct(text=x_nonce)
        signer = Account.recover_message(message, signature=x_signature)
    except Exception:
        raise HTTPException(401, "Invalid signature.")

    # Check NFT ownership on-chain
    nft = get_nft_contract(w3)
    try:
        owner = nft.functions.ownerOf(token_id).call()
    except Exception:
        raise HTTPException(404, f"Token {token_id} does not exist.")

    if Web3.to_checksum_address(owner) != Web3.to_checksum_address(signer):
        raise HTTPException(403, "Signer does not own this token.")

    # Read NFT metadata
    meta = nft.functions.getTokenMetadata(token_id).call()
    # TokenMetadata tuple: (agreementId, bandwidthMbps, durationSeconds, startTime, endpoint)
    agreement_id, bandwidth_mbps, duration_seconds, start_time, endpoint = meta

    # Read agreement status from escrow
    escrow = get_escrow_contract(w3)
    agreement = escrow.functions.getAgreement(agreement_id).call()
    # Agreement tuple: (consumer, provider, bandwidthMbps, durationSeconds, priceWei, requestDeadline, tokenId, status)
    status_code = agreement[7]
    STATUS_NAMES = {0: "NONE", 1: "REQUESTED", 2: "ACTIVE", 3: "CLOSED", 4: "CANCELLED"}

    elapsed = int(time.time()) - start_time
    seconds_remaining = max(0, duration_seconds - elapsed)

    return {
        "token_id": token_id,
        "agreement_id": agreement_id,
        "bandwidth_mbps": bandwidth_mbps,
        "duration_seconds": duration_seconds,
        "seconds_remaining": seconds_remaining,
        "status": STATUS_NAMES.get(status_code, "UNKNOWN"),
        "endpoint": endpoint,
        "signer": signer,
    }


if __name__ == "__main__":
    uvicorn.run("provider.gateway:app", host="0.0.0.0", port=8003, reload=False)

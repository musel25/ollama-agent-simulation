// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC721/utils/ERC721Holder.sol";
import "./BandwidthNFT.sol";

/**
 * @title BandwidthEscrow
 * @notice Double-escrow contract mediating ETH (consumer) <=> NFT (provider) swaps.
 *
 * State machine per agreement:
 *   NONE -> REQUESTED (consumer calls requestAgreement with msg.value)
 *        -> ACTIVE    (provider calls deposit; atomic swap fires inside deposit)
 *        -> CLOSED    (reserved for future use)
 *        -> CANCELLED (consumer or timeout trigger cancel)
 *
 * Note: the paper describes a PENDING state between provider deposit and swap.
 * Here the swap is atomic inside deposit(), so PENDING is never externally observable.
 */
contract BandwidthEscrow is ERC721Holder {
    enum Status {
        NONE,
        REQUESTED,
        ACTIVE,
        CLOSED,
        CANCELLED
    }

    struct Agreement {
        address consumer;
        address provider;
        uint256 bandwidthMbps;
        uint256 durationSeconds;
        uint256 priceWei;
        uint256 requestDeadline;
        uint256 tokenId;
        Status status;
    }

    BandwidthNFT public immutable nftContract;
    mapping(uint256 => Agreement) private _agreements;

    // ── Custom errors ──────────────────────────────────────────────────────────
    error AgreementAlreadyExists(uint256 agreementId);
    error AgreementNotFound(uint256 agreementId);
    error NotProvider();
    error NotConsumer();
    error WrongStatus(Status current, Status required);
    error DeadlineNotPassed();
    error MetadataMismatch();
    error ETHTransferFailed();
    error ZeroPriceNotAllowed();

    // ── Events ─────────────────────────────────────────────────────────────────
    event AgreementRequested(
        uint256 indexed agreementId,
        address indexed consumer,
        address indexed provider,
        uint256 bandwidthMbps,
        uint256 durationSeconds,
        uint256 priceWei
    );
    event AgreementActive(uint256 indexed agreementId, uint256 tokenId, address consumer, address provider);
    event AgreementCancelled(uint256 indexed agreementId, address indexed consumer);

    constructor(address _nftContract) {
        nftContract = BandwidthNFT(_nftContract);
    }

    /**
     * @notice Consumer locks ETH and creates a new agreement.
     */
    function requestAgreement(uint256 agreementId, address provider, uint256 bandwidthMbps, uint256 durationSeconds)
        external
        payable
    {
        if (_agreements[agreementId].status != Status.NONE) revert AgreementAlreadyExists(agreementId);
        if (msg.value == 0) revert ZeroPriceNotAllowed();

        _agreements[agreementId] = Agreement({
            consumer: msg.sender,
            provider: provider,
            bandwidthMbps: bandwidthMbps,
            durationSeconds: durationSeconds,
            priceWei: msg.value,
            requestDeadline: block.timestamp + 1 hours,
            tokenId: 0,
            status: Status.REQUESTED
        });

        emit AgreementRequested(agreementId, msg.sender, provider, bandwidthMbps, durationSeconds, msg.value);
    }

    /**
     * @notice Provider deposits the NFT and triggers the atomic swap.
     *         Checks-effects-interactions order: status updated BEFORE ETH transfer.
     */
    function deposit(uint256 agreementId, uint256 tokenId) external {
        Agreement storage ag = _agreements[agreementId];

        // ── Checks ────────────────────────────────────────────────────────────
        if (ag.status == Status.NONE) revert AgreementNotFound(agreementId);
        if (msg.sender != ag.provider) revert NotProvider();
        if (ag.status != Status.REQUESTED) revert WrongStatus(ag.status, Status.REQUESTED);

        BandwidthNFT.TokenMetadata memory meta = nftContract.getTokenMetadata(tokenId);
        if (
            meta.agreementId != agreementId || meta.bandwidthMbps != ag.bandwidthMbps
                || meta.durationSeconds != ag.durationSeconds
        ) {
            revert MetadataMismatch();
        }

        // ── Effects ───────────────────────────────────────────────────────────
        ag.status = Status.ACTIVE;
        ag.tokenId = tokenId;

        // ── Interactions ──────────────────────────────────────────────────────
        nftContract.safeTransferFrom(msg.sender, address(this), tokenId);
        nftContract.safeTransferFrom(address(this), ag.consumer, tokenId);
        (bool ok,) = ag.provider.call{value: ag.priceWei}("");
        if (!ok) revert ETHTransferFailed();

        emit AgreementActive(agreementId, tokenId, ag.consumer, ag.provider);
    }

    /**
     * @notice Cancel a REQUESTED agreement.
     *         Consumer may cancel at any time while REQUESTED.
     *         Anyone may cancel after requestDeadline.
     */
    function cancel(uint256 agreementId) external {
        Agreement storage ag = _agreements[agreementId];

        if (ag.status == Status.NONE) revert AgreementNotFound(agreementId);
        if (ag.status != Status.REQUESTED) revert WrongStatus(ag.status, Status.REQUESTED);

        bool isConsumer = msg.sender == ag.consumer;
        bool deadlinePassed = block.timestamp > ag.requestDeadline;
        if (!isConsumer && !deadlinePassed) revert DeadlineNotPassed();

        // Effects before interaction
        address consumer = ag.consumer;
        uint256 refund = ag.priceWei;
        ag.status = Status.CANCELLED;

        (bool ok,) = consumer.call{value: refund}("");
        if (!ok) revert ETHTransferFailed();

        emit AgreementCancelled(agreementId, consumer);
    }

    /// @notice Returns the full agreement struct.
    function getAgreement(uint256 agreementId) external view returns (Agreement memory) {
        return _agreements[agreementId];
    }

    receive() external payable {}
}

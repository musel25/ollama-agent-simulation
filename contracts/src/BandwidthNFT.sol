// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title BandwidthNFT
 * @notice ERC-721 token representing a bandwidth service entitlement.
 *         All metadata is stored on-chain; no tokenURI / IPFS.
 *         Only the contract owner (the provider EOA) may mint.
 */
contract BandwidthNFT is ERC721, Ownable {
    struct TokenMetadata {
        uint256 agreementId;
        uint256 bandwidthMbps;
        uint256 durationSeconds;
        uint256 startTime;
        string endpoint;
    }

    uint256 private _nextTokenId;
    mapping(uint256 => TokenMetadata) private _metadata;

    error TokenDoesNotExist(uint256 tokenId);

    constructor(address initialOwner) ERC721("BandwidthNFT", "BWNFT") Ownable(initialOwner) {}

    /**
     * @notice Mint a new bandwidth entitlement NFT. Only owner (provider) can call.
     * @return tokenId The newly minted token ID.
     */
    function mint(
        address to,
        uint256 agreementId,
        uint256 bandwidthMbps,
        uint256 durationSeconds,
        string calldata endpoint
    ) external onlyOwner returns (uint256 tokenId) {
        tokenId = _nextTokenId++;
        _safeMint(to, tokenId);
        _metadata[tokenId] = TokenMetadata({
            agreementId: agreementId,
            bandwidthMbps: bandwidthMbps,
            durationSeconds: durationSeconds,
            startTime: block.timestamp,
            endpoint: endpoint
        });
    }

    /// @notice Returns the on-chain metadata for a given token.
    function getTokenMetadata(uint256 tokenId) external view returns (TokenMetadata memory) {
        if (_ownerOf(tokenId) == address(0)) revert TokenDoesNotExist(tokenId);
        return _metadata[tokenId];
    }
}

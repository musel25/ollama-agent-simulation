// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Script.sol";
import "../src/BandwidthNFT.sol";
import "../src/BandwidthEscrow.sol";

contract Deploy is Script {
    function run() external {
        uint256 deployerKey = vm.envUint("DEPLOYER_PRIVATE_KEY");
        address providerAddress = vm.envAddress("PROVIDER_ADDRESS");

        vm.startBroadcast(deployerKey);

        BandwidthNFT nft = new BandwidthNFT(providerAddress);
        BandwidthEscrow escrow = new BandwidthEscrow(address(nft));

        vm.stopBroadcast();

        string memory json = string.concat(
            '{"bandwidthNFT":"', vm.toString(address(nft)), '","bandwidthEscrow":"', vm.toString(address(escrow)), '"}'
        );
        vm.writeFile("deployments/local.json", json);
    }
}

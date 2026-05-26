// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @notice Exercises every Solidity feature used by BandwidthEscrow, in miniature.
contract HelloWorld {
    address public owner;
    mapping(address => uint256) public greetings;

    event Greeted(address indexed who, uint256 count);
    error NotOwner();
    error SendSomething();

    constructor() {
        owner = msg.sender;
    }

    function greet() external payable {
        if (msg.value == 0) revert SendSomething();
        greetings[msg.sender] += 1;
        emit Greeted(msg.sender, greetings[msg.sender]);
    }

    function withdraw() external {
        if (msg.sender != owner) revert NotOwner();
        (bool ok, ) = msg.sender.call{value: address(this).balance}("");
        require(ok, "transfer failed");
    }
}

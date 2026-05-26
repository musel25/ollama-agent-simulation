// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @notice Tiny contract used to demonstrate deployment and state-changing calls.
contract Counter {
    uint256 public number;

    function increment() external {
        number += 1;
    }

    /// @notice Reverts when count would exceed 5. Used to demonstrate revert behavior.
    function incrementBounded() external {
        require(number < 5, "max reached");
        number += 1;
    }
}

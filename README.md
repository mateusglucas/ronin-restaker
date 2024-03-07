# ronin-staker
Automatically restake staking pools rewards

# Description

[Ronin](https://roninchain.com/) is an EVM blockchain specifically forged for gaming. Staking pools in this blockchain enable users to lock up (stake) their tokens and receive newly created tokens as rewards.

This package allows the user to automatically restake the earned rewards from [Katana staking pools](https://katana.roninchain.com/#/farm) and from [AXS staking pool](https://stake.axieinfinity.com/).

Two staking strategies are provided:
* ASAP: restake the rewards *as soon as possible* (every 24 hours).
* OptimalInterval: estimate restaking fees and calculate the optimal interval to maximize the compound interest.

The OptimalInterval strategy also allows you to specify a target minimum RON balance to avoid zeroing the RON balance in the long run due to paying fees. When using Katana staking pools with a RON balance lower than the target balance, this strategy will use the rewards in the long run to correct the RON balance so that it follows closely the specified target.

# How to use

You can use the `restaker` and `strategy` modules to create your own application or use the provided `main.py` script.

The provided script needs your Ronin wallet private key in order to send the signed transactions to restake your earnings. Your private key will be stored using the [Python keyring library](https://pypi.org/project/keyring/).

**PROVIDING YOUR PRIVATE KEY COULD ALLOW ALL YOUR ASSETS IN YOUR WALLET TO BE STOLEN. DO IT AT YOUR OWN RISK.**

Run `pip install -r requirements.txt` to install the dependencies.

Run `python main.py` and follow the instructions.

If you want to change the wallet, just re-run `main.py` and select the option to set your private key, overwriting the old one.

# Donations

If this project is useful for you and you want to buy me a coffee:

Ronin: `ronin:5c3d4f872ef61b1e50e99e2c9bb38cb3054c99f5`

Ethereum or BSC: `0xDD8d5E347a7Ee6e6197B17b8312Ec9A58E754648`

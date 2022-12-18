# axs-auto-staker
Automatically restake AXS rewards

# Description

Axie Infinity Shards (AXS) are an ERC 20 governance token for the Axie universe (https://axieinfinity.com/axs/). Users are able to lock up (stake) their AXS tokens and receive newly created AXS as reward (https://stake.axieinfinity.com/), which can be claimed or restaked every 24 hours.

This script automatically restakes the earned rewards every time they become available.

# How to use

This script needs your Ronin wallet private key in order to send the signed transactions to restake your earnings.

**PROVIDING YOUR PRIVATE KEY COULD ALLOW ALL YOUR ASSETS IN YOUR WALLET TO BE STOLEN. DO IT AT YOUR OWN RISK.**

Run `python3 config_priv_key.py`, follow the instructions and paste your private key as an hex string ('0x...'). Your private key will be stored using the [Python keyring library](https://pypi.org/project/keyring/).

After the step above, run `python3 axs_auto_staker.py` to start the auto-staker.

If you want to change the wallet, just repeat the steps above, providing the private key of the new wallet.

# Donations

If this script is useful for you and you want to buy me a coffee:

Ronin: `ronin:5c3d4f872ef61b1e50e99e2c9bb38cb3054c99f5`

Ethereum or BSC: `0xDD8d5E347a7Ee6e6197B17b8312Ec9A58E754648`

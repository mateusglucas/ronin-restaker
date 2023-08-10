from web3 import Web3
import utils
from .restaker import Restaker

class AXSRestaker(Restaker):
    _axs_staking_pool_addr = Web3.toChecksumAddress('0x05b0bb3c1c320b280501b86706c3551995bc8571')

    def __init__(self, priv_key):
        super().__init__(priv_key, AXSRestaker._axs_staking_pool_addr)

    @classmethod
    def _is_staking_token_lp_token(cls):
        return False
    
    def _estimate_gas_to_restake(self, N=10):
        gas_estimated = utils.estimate_gas_used(self.staking_pool.functions.restakeRewards, N = N)
        return gas_estimated

    def restake_rewards(self):
        restake_call = self.staking_pool.functions.restakeRewards()

        restake_txn_hash = self._send_signed_transaction(restake_call)
        restake_txn_rec = self._wait_txn_receipt(restake_txn_hash)

        gas_used = restake_txn_rec['gasUsed'] # TODO: printar

        if restake_txn_rec['status'] == 0:
            raise Exception('restake rewards failed')

        log = Restaker._get_log_from_receipt(restake_txn_rec, self.staking_pool.events.RewardClaimed())
        restaked_reward = log.args._amount

        return restaked_reward, gas_used
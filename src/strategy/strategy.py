from logger import Logger
from restaker import Restaker, KatanaRestaker, AXSRestaker

class Strategy:

    def __init__(self, restaker : Restaker):
        self.restaker = restaker
        self.logger = Logger('log_{}.txt'.format(restaker.staking_token_symbol))

    def _print(self, msg):
        self.logger.print(msg)

    def _print_exception(self, e : Exception):
        self._print('{}: {}'.format(e.__class__.__name__,
                                            e.__str__()))

    def run(self):
        self._print('##### Restaker #####')
        self._print('Strategy: {}'.format(self.__class__.__name__))
        self._print('Staking pool: {} ({})'.format(self.restaker.staking_token_symbol,
                                                   self.restaker.staking_pool.address))
        self._print('Wallet: {}'.format(self.restaker.wallet.address))

        while True:
            try:
                self._loop()
            except BaseException as e:
                self._print_exception(e)
                raise e

    def _loop(self):
        raise NotImplemented('loop not implemented')

    def _is_ron_balance_low(self, fees_estimated_ron):
        restaker : Restaker = self.restaker
        ron_balance = restaker.ronin_chain.eth.get_balance(restaker.wallet.address)
        # Using 2x margin for fee estimation vs. real fee
        if 2*fees_estimated_ron > ron_balance:
            # Using 4x margin for variability in fee estimation in the next loop, to not fall here again
            self._print('RON balance too low. Deposit at least {} RON to continue.'.format((4*fees_estimated_ron-ron_balance)*10**(-restaker.wron_token_decimals)))
            return True
        else:
            return False
        
    def _estimate_fees_ron(self, pending_rewards_ron, gas_estimated_ron):
        restaker : Restaker = self.restaker

        if isinstance(restaker, KatanaRestaker):
            swap_fees_ron = (pending_rewards_ron - gas_estimated_ron)/2 * 0.003 # 0.3 % swap fees
        elif isinstance(restaker, AXSRestaker):
            swap_fees_ron = 0 # no swap
        else:
            raise NotImplementedError('not implemented for {} class'.format(restaker.__class__.__name__))
        fees_estimated_ron = gas_estimated_ron + swap_fees_ron

        return fees_estimated_ron
    
    def _restake(self):
        restaker = self.restaker
        if isinstance(restaker, KatanaRestaker):
            return self._katana_restake()
        elif isinstance(restaker, AXSRestaker):
            return self._axs_restake()
        else:
            raise NotImplementedError('restaking strategy not implemented for {} class'.format(restaker.__class__.__name__))

    def _katana_restake(self):
        assert isinstance(self.restaker, KatanaRestaker), '{} class different from {}'.format(self.restaker.__class__.__name__,
                                                                                              KatanaRestaker.__name__)
        restaker : KatanaRestaker = self.restaker

        self._print('Claiming rewards...')
        claimed_reward, gas_used_claim = restaker.claim_rewards()
        self._print('Claimed {} {}.'.format(claimed_reward, restaker.reward_token_symbol))

        usable_reward = self._get_usable_reward(claimed_reward, gas_used_claim)

        reward_to_swap = round(usable_reward/2)
        self._print('Swapping {} {}...'.format(reward_to_swap, restaker.reward_token_symbol))
        swapped_amount, gas_used_swap = restaker.swap_ron_for_token(reward_to_swap)

        token = restaker.token1 if restaker.token0.address == restaker.wron_token.address else restaker.token0
        _, [token_decimals, token_symbol] = restaker.multicall2.aggregate([token.functions.decimals(),
                                                                         token.functions.symbol()]).call()
        self._print('Swapped {} {}.'.format(swapped_amount*10**(-token_decimals), token_symbol))

        self._print('Adding liquidity...')
        minted_amount, gas_used_add_liquidity = restaker.add_liquidity(swapped_amount)
        self._print('Minted {} {}.'.format(minted_amount, restaker.staking_token_symbol))

        self._print('Staking {} {}...'.format(minted_amount, restaker.staking_token_symbol))
        gas_used_stake = restaker.stake(minted_amount)
        self._print('Staked {} {}.'.format(minted_amount, restaker.staking_token_symbol))

        return gas_used_claim + gas_used_swap + gas_used_add_liquidity + gas_used_stake

    def _get_usable_reward(self, claimed_reward, gas_used_claim):
        return claimed_reward

    def _axs_restake(self):
        assert isinstance(self.restaker, AXSRestaker), '{} class not instance of {}'.format(self.restaker.__class__.__name__,
                                                                                            AXSRestaker.__name__)
        restaker : AXSRestaker = self.restaker
        
        self._print('Restaking rewards...')
        restaked_rewards, gas_used_restake = restaker.restake_rewards()
        self._print('Restaked {} {}.'.format(restaked_rewards, restaker.staking_token_symbol))

        return gas_used_restake
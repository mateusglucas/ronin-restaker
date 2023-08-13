from .strategy import Strategy
from restaker import Restaker, KatanaRestaker, AXSRestaker
from time import time, sleep

class IntervalStrategy(Strategy):

    def __init__(self, restaker : Restaker):
        super().__init__(restaker)

    def _loop(self):
        restaker = self.restaker
        r = restaker.multicall2.aggregate([
                    restaker.staking_pool.functions.getPendingRewards(restaker.wallet.address),
                    restaker.staking_pool.functions.getStakingAmount(restaker.wallet.address),
                    restaker.staking_manager.functions.userRewardInfo(restaker.staking_pool.address, restaker.wallet.address),
                    restaker.staking_manager.functions.canObtainRewards(restaker.staking_pool.address, restaker.wallet.address),
                    restaker.staking_manager.functions.minClaimedTimeWindow()]).call()
        block_number = r[0]
        pending_rewards = r[1][0]
        staking_amount = r[1][1]
        last_claimed_timestamp = r[1][2][2]
        can_claim_rewards = r[1][3]
        min_claimed_time_window = r[1][4]

        # TODO: futuramente, calcular todos preços internamente ao chain, calculando em relação a USDC (ou RON)
        # TODO: tentar usar get https://exchange-rate.axieinfinity.com/
        staking_token_price, reward_token_price, wron_token_price = restaker._get_tokens_prices_usd()

        gain_rate = restaker._get_gain_rate(reward_token_price/staking_token_price, N=28800)
        self._print('Estimated APR: {:.2f}%'.format(100*gain_rate*60*60*24*365))

        staked_ron = staking_amount * staking_token_price/wron_token_price
        staked_usd = staking_amount*staking_token_price*10**(-restaker.staking_token_decimals)
        self._print('Staked amount: {} {} ({} USD)'.format(staking_amount*10**(-restaker.staking_token_decimals),
                                                           restaker.staking_token_symbol,
                                                           staked_usd))
        
        rewards_ron = pending_rewards * reward_token_price/wron_token_price
        rewards_usd = pending_rewards*reward_token_price*10**(-restaker.reward_token_decimals)
        self._print('Claimable rewards: {} {} ({} USD)'.format(pending_rewards*10**(-restaker.reward_token_decimals),
                                                               restaker.reward_token_symbol,
                                                                rewards_usd))

        gas_price_ron = restaker.ronin_chain.eth.gas_price
        gas_price_usd = gas_price_ron*wron_token_price*10**(-restaker.wron_token_decimals)
        gas_estimated = restaker._estimate_gas_to_restake()
        gas_estimated_ron = gas_estimated * gas_price_ron
        gas_estimated_usd = gas_estimated * gas_price_usd
        self._print('Estimated gas to restake: {} ({} USD)'.format(gas_estimated, gas_estimated_usd))

        last_claim_elapsed_time = time() - last_claimed_timestamp

        # total fees are not always a function of gas only, but sometimes also of pending reward, because
        # some restakers need to swap tokens (0.3% fee)
        rewards_ron = pending_rewards * reward_token_price/wron_token_price
        fees_estimated_ron = self._estimate_fees_ron(rewards_ron, gas_estimated_ron)
        if self._is_ron_balance_low(fees_estimated_ron):
            self._print('Sleeping for 10 minutes...')
            sleep(10*60) # sleep for 10 minutes
            return
        
        time_to_restake = self._get_time_to_restake(rewards_ron, fees_estimated_ron, staked_ron, gain_rate)

        if time_to_restake <= 0:
            if can_claim_rewards:
                self._print('Restaking...')
                gas_used = self._restake()
                self._print('Total gas used: {} ({} USD)'.format(gas_used,
                                                                gas_used*gas_price_usd))
                self._print('Gas estimation error: {:.2f}%'.format(100*(gas_used-gas_estimated)/gas_estimated))
                sleep_time = 60*60*24
            elif last_claim_elapsed_time < min_claimed_time_window:
                time_to_allow_restake = max(0, min_claimed_time_window - last_claim_elapsed_time)
                self._print('Remaining time to be allowed to restake: {:.2f} days'.format(time_to_allow_restake/60/60/24))
                sleep_time = time_to_allow_restake
            else:
                self._print('Can not restake yet and we do not know why!')
                sleep_time = 60*60*24
        else:
            self._print('Remaining time to restake: {:.2f} days'.format(time_to_restake/60/60/24))
            sleep_time = min(time_to_restake, 60*60*24)

        self._print('Sleeping for {:.2f} days...'.format(sleep_time/60/60/24))
        sleep(sleep_time)

    def _get_time_to_restake(self, rewards_ron, fees_estimated_ron, staked_ron, gain_rate):
        raise Exception('not implemented')

    def _restake(self):
        restaker = self.restaker
        if isinstance(restaker, KatanaRestaker):
            return self._katana_restake()
        elif isinstance(restaker, AXSRestaker):
            return self._axs_restake()
        else:
            raise NotImplementedError('restaking strategy not implemented for {} class'.format(restaker.__class__.__name__))

    def _katana_restake(self):
        assert isinstance(self.restaker, KatanaRestaker), '{} class not instance of {}'.format(self.restaker.__class__.__name__,
                                                                                               KatanaRestaker.__name__)
        restaker : KatanaRestaker = self.restaker

        self._print('Claiming rewards...')
        claimed_reward, gas_used_claim = restaker.claim_rewards()
        self._print('Claimed {} {}.'.format(claimed_reward*10**(-restaker.reward_token_decimals), restaker.reward_token_symbol))

        reward_to_swap = round(claimed_reward/2)
        self._print('Swapping {} {}...'.format(reward_to_swap*10**(-restaker.reward_token_decimals), restaker.reward_token_symbol))
        swapped_amount, gas_used_swap = restaker.swap_ron_for_token(reward_to_swap)

        token = restaker.token1 if restaker.token0.address == restaker.wron_token.address else restaker.token0
        _, [token_decimals, token_symbol] = restaker.multicall2.aggregate([token.functions.decimals(),
                                                                         token.functions.symbol()]).call()
        self._print('Swapped {} {}.'.format(swapped_amount*10**(-token_decimals), token_symbol))

        self._print('Adding liquidity...')
        minted_amount, gas_used_add_liquidity = restaker.add_liquidity(swapped_amount)
        self._print('Minted {} {}.'.format(minted_amount*10**(-restaker.staking_token_decimals), restaker.staking_token_symbol))

        self._print('Staking {} {}...'.format(minted_amount*10**(-restaker.staking_token_decimals), restaker.staking_token_symbol))
        gas_used_stake = restaker.stake(minted_amount)
        self._print('Staked {} {}.'.format(minted_amount*10**(-restaker.staking_token_decimals), restaker.staking_token_symbol))

        return gas_used_claim + gas_used_swap + gas_used_add_liquidity + gas_used_stake

    def _axs_restake(self):
        assert isinstance(self.restaker, AXSRestaker), '{} class not instance of {}'.format(self.restaker.__class__.__name__,
                                                                                            AXSRestaker.__name__)
        restaker : AXSRestaker = self.restaker
        
        self._print('Restaking rewards...')
        restaked_rewards, gas_used_restake = restaker.restake_rewards()
        self._print('Restaked {} {}.'.format(restaked_rewards, restaker.staking_token_symbol))

        return gas_used_restake
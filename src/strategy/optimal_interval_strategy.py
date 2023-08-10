from time import time, sleep
from restaker import Restaker, KatanaRestaker, AXSRestaker
from .strategy import Strategy

class OptimalIntervalStrategy(Strategy):

    def __init__(self, restaker : Restaker, min_desired_ron_balance = 0):
        super().__init__(restaker)
        self.min_desired_ron_balance = min_desired_ron_balance
        pass

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

        staked_usd = staking_amount*staking_token_price*10**(-restaker.staking_token_decimals)
        rewards_usd = pending_rewards*reward_token_price*10**(-restaker.reward_token_decimals)

        gas_price_ron = restaker.ronin_chain.eth.gas_price
        gas_price_usd = gas_price_ron*wron_token_price*10**(-restaker.wron_token_decimals)
        gas_estimated = restaker._estimate_gas_to_restake() # TODO: printar
        swap_fees = pending_rewards/2 * 0.003 # 0.3 % swap fees
        fees_estimated_ron = gas_estimated * gas_price_ron + swap_fees

        ron_balance = restaker.ronin_chain.eth.get_balance(restaker.wallet.address)
        if 2*fees_estimated_ron > ron_balance:
            # Using:
            # 2x margin for fee estimation vs. real fee
            # 4x margin for variability in fee estimation in the next loop, to not fall here again
            self._print('RON balance too low. Deposit at least {} RON to continue.'.format((4*fees_estimated_ron-ron_balance)*10**(-restaker.wron_token_decimals)))
            self._print('Sleeping for 10 minutes...')
            sleep(10*60) # sleep for 10 minutes
            return

        # readjust fees to penalize min_desired_ron_balance negative deviation
        pending_rewards_ron = pending_rewards*reward_token_price/wron_token_price
        usable_ron_balance = self._get_usable_ron_balance(pending_rewards_ron)
        fees_estimated_ron = fees_estimated_ron + max(0, -usable_ron_balance)
        fees_estimated_usd = fees_estimated_ron*wron_token_price*10**(-restaker.wron_token_decimals)

        # In situations where the user stopped to stake tokens for a while or when the user 
        # never claimed rewards at all, the true elapsed time (time() - last_claimed_timestamp) 
        # isn't a good estimator of how long the user is staking the tokens that are in the wallet
        # right now. A more realistic estimator is obtained dividing the actual gains by the gain rate
        # of the pool in the last 24 hours (~28800 blocks). This estimator is better but isn't perfect:
        # - if the user stake more tokens in the middle of the period, it will underestimate the time;
        # - if the user unstake some tokens in the middle of the period, it will overestimate the time.
        gain = rewards_usd/staked_usd
        gain_rate = restaker._get_gain_rate(block_number, reward_token_price/staking_token_price, N=28800)
        estimated_elapsed_time = gain/gain_rate
        optimal_interval = OptimalIntervalStrategy._estimate_optimal_restake_interval(fees_estimated_usd/staked_usd, gain_rate)
        estimated_remaining_time = max(0, optimal_interval - estimated_elapsed_time)

        elapsed_time = time() - last_claimed_timestamp
        remaining_time_to_restake = max(0, min_claimed_time_window - elapsed_time)

        self._print('Estimated APR: {:.2f}%'.format(100*gain_rate*60*60*24*365))
        self._print('Estimated gas: {} ({} USD)'.format(gas_estimated, fees_estimated_usd))
        self._print('Staked amount: {} {} ({} USD)'.format(staking_amount*10**(-restaker.staking_token_decimals),
                                                           restaker.staking_token_symbol,
                                                           staked_usd))
        self._print('Claimable rewards: {} {} ({} USD)'.format(pending_rewards*10**(-restaker.reward_token_decimals),
                                                               restaker.reward_token_symbol,
                                                                rewards_usd))
        self._print('Remaining time to be able to restake: {:.2f} days'.format(remaining_time_to_restake/60/60/24))
        self._print('Optimal restake interval: {:.2f} days'.format(optimal_interval/60/60/24))
        self._print('Estimated elapsed time: {:.2f} days'.format(estimated_elapsed_time/60/60/24))

        if estimated_remaining_time <= 0 and can_claim_rewards == True:
            self._print('Restaking...')

            gas_used = self._restake()

            self._print('Total gas used: {} ({} USD)'.format(gas_used,
                                                             gas_used*gas_price_usd))
            self._print('Gas estimation error: {:.2f}%'.format(100*(gas_used-gas_estimated)/gas_estimated))
        else:
            if elapsed_time < min_claimed_time_window:
                self._print('Elapsed time smaller than min claimed time window ({} days)'.format(min_claimed_time_window/60/60/24))
                time_to_sleep = min_claimed_time_window - elapsed_time
            elif elapsed_time > 0:
                self._print('Remaining time: {:.2f} days'.format(remaining_time_to_restake/60/60/24))
                time_to_sleep = min(remaining_time_to_restake, 60*60*24)
            else:
                self._print('Can not restake yet and we do not know why!')
                time_to_sleep = 60*60*24
            self._print('Sleeping for {:.2f} days...'.format(time_to_sleep/60/60/24))
            sleep(time_to_sleep)

    # fee_ratio: razão entre custo para restaking e montante inicial
    # gain_rate: proporção de crescimento por intervalo de tempo
    @staticmethod
    def _estimate_optimal_restake_interval(fee_ratio, gain_rate):
        u=1-fee_ratio

        h = lambda x: exp(x/(x+u))-x-u
        dh = lambda x: exp(x/(x+u))*(1/(x+u)-x/(x+u)**2)-1

        tol=1e-6 # tolerante, in units of time

        iter=0

        x0 = 1
        x1 = x0-h(x0)/dh(x0) 

        # time interval is x/k, so the tolerance is compared
        # against x/k
        while abs(x1-x0)/gain_rate>tol and iter<100:
            x0=x1
            x1=x0-h(x0)/dh(x0)
            iter+=1

        if abs(x1-x0)/gain_rate>tol:
            raise Exception('solution not found')
        else:
            return x1/gain_rate

    def _get_usable_ron_balance(self, pending_rewards_ron):
        restaker = self.restaker
        ron_balance = restaker.ronin_chain.eth.get_balance(restaker.wallet.address)
        usable_ron_balance = ron_balance - self.min_desired_ron_balance*10**restaker.wron_token_decimals
        if self._is_reward_added_to_ron_balance():
            usable_ron_balance += pending_rewards_ron
        return usable_ron_balance

    def _is_reward_added_to_ron_balance(self):
        restaker = self.restaker
        if restaker.__class__ is KatanaRestaker:
            return True
        elif restaker.__class__ is AXSRestaker:
            return False
        else:
            raise NotImplementedError('method not implemented for {} class'.format(restaker.__class__.__name__))

    def _restake(self):
        restaker = self.restaker
        if isinstance(restaker, KatanaRestaker):
            return self._katana_restake()
        elif isinstance(restaker, AXSRestaker):
            return self._axs_restake()
        else:
            raise NotImplementedError('restaking strategy not implemented for {} class'.format(restaker.__class__.__name__))

    def _katana_restake(self):
        assert self.restaker.__class__ is KatanaRestaker, '{} class different from {}'.format(self.restaker.__class__.__name__,
                                                                                              KatanaRestaker.__name__)
        restaker : KatanaRestaker = self.restaker

        self._print('Claiming rewards...')
        claimed_reward, gas_used_claim = restaker.claim_rewards()
        self._print('Claimed {} {}.'.format(claimed_reward, restaker.reward_token_symbol))

        self._print('Estimating usable rewards...')
        gas_price = restaker.ronin_chain.eth.gas_price
        gas_estimated = restaker._estimate_gas_to_restake()
        fees_estimated_ron =  gas_price * gas_estimated
        usable_reward = claimed_reward - fees_estimated_ron
        if usable_reward <= 0:
            self._print('Claimed rewards lower than predicted restaking fees.')
            self._print('Restaking aborted.')
            return
        estimated_remaining_fees_ron = fees_estimated_ron - gas_used_claim * gas_price
        ron_balance = restaker.ronin_chain.eth.get_balance(restaker.wallet.address)
        # Here it is! The control loop to make the RON balance follow the min_desired_ron_balance closely
        deviation_from_desired_ron_balance = ron_balance - estimated_remaining_fees_ron - self.min_desired_ron_balance*10**restaker.wron_token_decimals
        usable_reward = min(usable_reward, deviation_from_desired_ron_balance)
        if usable_reward <= 0:
            self._print('All claimed rewards used to reach desired RON balance.')
            self._print('Restaking aborted.')
            return
        self._print('Usable rewards: {} {}.'.format(usable_reward, restaker.reward_token_symbol))

        reward_to_swap = round(usable_reward/2)
        self._print('Swapping {} {}...'.format(reward_to_swap, restaker.reward_token_symbol))
        swapped_amount, gas_used_swap = restaker.swap_ron_for_token(reward_to_swap)
        self._print('Swapped {} {}.'.format(swapped_amount, restaker.reward_token_symbol))

        self._print('Adding liquidity...')
        minted_amount, gas_used_add_liquidity = restaker.add_liquidity(swapped_amount)
        self._print('Minted {} {}.'.format(minted_amount, restaker.staking_token_symbol))

        self._print('Staking {} {}...'.format(minted_amount, restaker.staking_token_symbol))
        gas_used_stake = restaker.stake(minted_amount)
        self._print('Staked {} {}.'.format(minted_amount, restaker.staking_token_symbol))

        return gas_used_claim + gas_used_swap + gas_used_add_liquidity + gas_used_stake

    def _axs_restake(self):
        assert self.restaker.__class__ is AXSRestaker, '{} class different from {}'.format(self.restaker.__class__.__name__,
                                                                                           AXSRestaker.__name__)
        restaker : AXSRestaker = self.restaker
        
        self._print('Restaking rewards...')
        restaked_rewards, gas_used_restake = restaker.restake_rewards()
        self._print('Restaked {} {}.'.format(restaked_rewards, restaker.staking_token_symbol))

        return gas_used_restake


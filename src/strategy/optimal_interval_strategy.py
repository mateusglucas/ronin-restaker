from restaker import Restaker, KatanaRestaker, AXSRestaker
from .interval_strategy import IntervalStrategy
from math import exp

class OptimalIntervalStrategy(IntervalStrategy):

    def __init__(self, restaker : Restaker, min_desired_ron_balance = 0):
        super().__init__(restaker)
        self.min_desired_ron_balance = min_desired_ron_balance

    def _get_time_to_restake(self, rewards_ron, fees_estimated_ron, staked_ron, gain_rate):
        # readjust fees to penalize min_desired_ron_balance negative deviation
        usable_ron_balance = self._get_usable_ron_balance(rewards_ron)
        fees_estimated_ron = fees_estimated_ron + max(0, -usable_ron_balance)

        # In situations where the user stopped to stake tokens for a while or when the user 
        # never claimed rewards at all, the true elapsed time (time() - last_claimed_timestamp) 
        # isn't a good estimator of how long the user is staking the tokens that are in the wallet
        # right now. A more realistic estimator is obtained dividing the actual gains by the gain rate
        # of the pool in the last 24 hours (~28800 blocks). This estimator is better but isn't perfect:
        # - if the user stake more tokens in the middle of the period, it will underestimate the time;
        # - if the user unstake some tokens in the middle of the period, it will overestimate the time.
        gain = rewards_ron/staked_ron
        estimated_elapsed_time = gain/gain_rate
        self._print('Estimated elapsed time: {:.2f} days'.format(estimated_elapsed_time/60/60/24))

        optimal_interval = self._estimate_optimal_restake_interval(fees_estimated_ron/staked_ron, gain_rate)
        self._print('Optimal restake interval: {:.2f} days'.format(optimal_interval/60/60/24))

        time_to_restake = max(0, optimal_interval - estimated_elapsed_time)
        self._print('Time to restake: {:.2f} days'.format(time_to_restake/60/60/24))

        return time_to_restake

    # fee_ratio: razão entre custo para restaking e montante inicial
    # gain_rate: proporção de crescimento por intervalo de tempo
    @staticmethod
    def _estimate_optimal_restake_interval(fee_ratio, gain_rate):
        u=1-fee_ratio

        h = lambda x: exp(x/(x+u))-x-u
        dh = lambda x: exp(x/(x+u))*(1/(x+u)-x/(x+u)**2)-1

        tol=1e-6 # step relative tolerance

        x0 = 1
        x1 = x0-h(x0)/dh(x0) 

        iter=0
        converged = False
        while iter<100:
            mean_abs = (abs(x0) + abs(x1))/2
            if mean_abs==0: # if mean_abs==0, then x0==x1==0
                converged = True
                break

            step = x1-x0
            relative_step = abs(step)/mean_abs
            if relative_step < tol:
                converged = True
                break

            x0=x1
            x1=x0-h(x0)/dh(x0)

            iter+=1
        
        if not converged:
            Warning('solution not satisfying tolerances: x0={}, x1={}, tol={}'.format(x0, x1, tol))

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
        if isinstance(restaker, KatanaRestaker):
            return True
        elif isinstance(restaker, AXSRestaker):
            return False
        else:
            raise NotImplementedError('method not implemented for {} class'.format(restaker.__class__.__name__))

    def _get_usable_reward(self, claimed_reward, gas_used_claim):
        restaker : KatanaRestaker = self.restaker

        assert restaker.reward_token.address.lower() == Restaker._wron_token_addr.lower(), 'Reward token is not WRON!'

        self._print('Estimating usable rewards...')
        gas_price_ron = restaker.ronin_chain.eth.gas_price
        gas_estimated = restaker._estimate_gas_to_restake()
        gas_estimated_ron = gas_price_ron * gas_estimated
        usable_reward = claimed_reward - gas_estimated_ron
        if usable_reward <= 0:
            self._print('Claimed rewards lower than estimated gas fees.')
            self._print('Restaking aborted.')
            return
        estimated_remaining_gas_ron = gas_estimated_ron - gas_used_claim * gas_price_ron
        ron_balance = restaker.ronin_chain.eth.get_balance(restaker.wallet.address)
        # Here it is! The control loop to make the RON balance follow the min_desired_ron_balance closely
        deviation_from_desired_ron_balance = ron_balance - estimated_remaining_gas_ron - self.min_desired_ron_balance*10**restaker.wron_token_decimals
        usable_reward = min(usable_reward, deviation_from_desired_ron_balance)
        if usable_reward <= 0:
            self._print('All claimed rewards used to reach desired RON balance.')
            self._print('Restaking aborted.')
            return
        self._print('Usable rewards: {} {}.'.format(usable_reward*10**(-restaker.wron_token_decimals), restaker.reward_token_symbol))

        return usable_reward
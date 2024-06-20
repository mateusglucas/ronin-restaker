import utils
from time import time
from .restaker import Restaker

class KatanaRestaker(Restaker):
   
    def __init__(self, priv_key, staking_pool_addr):
        super().__init__(priv_key, staking_pool_addr) 

    @classmethod
    def _is_staking_token_lp_token(cls):
        return True
    
    def _estimate_gas_to_restake(self, N=10):
        gas_estimated = utils.estimate_gas_used(self.staking_pool.functions.claimPendingRewards, N = N)
        gas_estimated += utils.estimate_gas_used(self.permissioned_router.functions.swapExactRONForTokens, N = N)  
        gas_estimated += utils.estimate_gas_used(self.permissioned_router.functions.addLiquidityRON, N = N)
        gas_estimated += utils.estimate_gas_used(self.staking_pool.functions.stake, N = N)
        return gas_estimated

    def claim_rewards(self):
        claim_call = self.staking_pool.functions.claimPendingRewards()

        claim_txn_hash = self._send_signed_transaction(claim_call)
        claim_txn_rec = self._wait_txn_receipt(claim_txn_hash)

        gas_used = claim_txn_rec['gasUsed'] # TODO: printar

        if claim_txn_rec['status'] == 0:
            raise Exception('claim rewards failed')

        log = Restaker._get_log_from_receipt(claim_txn_rec, self.staking_pool.events.RewardClaimed())
        claimed_reward = log.args._amount

        return claimed_reward, gas_used

    def swap_ron_for_token(self, ron_to_swap):
        if self.reward_token.address == self.token1.address:
            token = self.token0
            token_price = self._get_token0_price_from_lp()
        else:
            token = self.token1
            token_price = self._get_token1_price_from_lp()

        slippage = 0.01
        deadline = 30*60 # 30 minutes

        token_amount = round(ron_to_swap/token_price)*(1-0.003) # 0.3% swap fee

        swap_call = self.permissioned_router.functions.swapExactRONForTokens(round((1-slippage)*token_amount), 
                                                                [self.reward_token.address, token.address], 
                                                                self.wallet.address, 
                                                                round(time()+deadline))
        swap_params = {'value': ron_to_swap}

        swap_txn_hash = self._send_signed_transaction(swap_call, swap_params)
        swap_txn_rec = self._wait_txn_receipt(swap_txn_hash)

        gas_used = swap_txn_rec['gasUsed'] # TODO: printar

        if swap_txn_rec['status'] == 0:
            raise Exception('swap failed')
        
        log = Restaker._get_log_from_receipt(swap_txn_rec, self.staking_token.events.Swap())
        key = '_amount{}Out'.format('0' if token.address == self.token0.address else '1')
        swapped_amount = log.args[key]

        return swapped_amount, gas_used

    def add_liquidity(self, token_amount):
        if self.reward_token.address == self.token1.address:
            token = self.token0
            ron_amount = round(self._get_token0_price_from_lp()*token_amount)
        else:
            token = self.token1
            ron_amount = round(self._get_token1_price_from_lp()*token_amount)

        deadline = 30*60 # 30 minutes
        slippage = 0.01

        liquidity_call = self.permissioned_router.functions.addLiquidityRON(token.address,
                                                                    token_amount,
                                                                    token_amount,
                                                                    round(ron_amount*(1-slippage)),
                                                                    self.wallet.address,
                                                                    round(time()+deadline))
        liquidity_params = {'value': round(ron_amount*(1+slippage))}

        liquidity_txn_hash = self._send_signed_transaction(liquidity_call, liquidity_params)
        liquidity_txn_rec = self._wait_txn_receipt(liquidity_txn_hash)

        gas_used = liquidity_txn_rec['gasUsed'] # TODO: printar

        if liquidity_txn_rec['status'] == 0:
            raise Exception('add liquidity failed')

        log = Restaker._get_log_from_receipt(liquidity_txn_rec, self.staking_token.events.Transfer())
        minted_amount = log.args._value

        return minted_amount, gas_used

    def stake(self, amount_to_stake):
        stake_call = self.staking_pool.functions.stake(amount_to_stake)

        stake_txn_hash = self._send_signed_transaction(stake_call)
        stake_txn_rec = self._wait_txn_receipt(stake_txn_hash)

        gas_used = stake_txn_rec['gasUsed'] # TODO: printar

        if stake_txn_rec['status'] == 0:
            raise Exception('stake failed')
        
        return gas_used

    def _get_token0_price_from_lp(self, N = 20):
        return self._get_token_price_from_lp(0, N = N)

    def _get_token1_price_from_lp(self, N = 20):
        return self._get_token_price_from_lp(1, N = N)
    
    def _get_token_price_from_lp(self, idx, N = 20):
        func = self.staking_token.get_function_by_name('price{}CumulativeLast'.format(idx))

        block_number, [reserves, price_t1] = self.multicall2.aggregate([
            self.staking_token.functions.getReserves(),
            func()
        ]).call()

        price_t0 = func().call(block_identifier = block_number - N)  

        # if cumulative price changed, calculate TWAP
        # else, use reserves ratio
        # TODO: TWAP price too high. Debug
        if False: # price_t1-price_t0 != 0:
            t1 = self.ronin_chain.eth.get_block(block_number)['timestamp']
            t0 = self.ronin_chain.eth.get_block(block_number - N)['timestamp']
            price = (price_t1 - price_t0)/(t1 - t0)
        else:
            price = reserves[1-idx]/reserves[idx]

        return price
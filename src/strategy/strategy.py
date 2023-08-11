from logger import Logger
from restaker import Restaker, KatanaRestaker, AXSRestaker
from time import sleep

class Strategy:

    def __init__(self, restaker : Restaker):
        self.restaker = restaker
        self.logger = Logger('log_{}.txt'.format(restaker.staking_token_symbol))
        pass

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
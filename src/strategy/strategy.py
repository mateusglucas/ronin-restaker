from logger import Logger
from restaker import Restaker

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

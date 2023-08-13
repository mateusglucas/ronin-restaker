from time import time, sleep
from restaker import Restaker, KatanaRestaker, AXSRestaker
from .interval_strategy import IntervalStrategy

class ASAPStrategy(IntervalStrategy):

    def __init__(self, restaker : Restaker):
        super().__init__(restaker)

    def _get_time_to_restake(self, rewards_ron, fees_estimated_ron, staked_ron, gain_rate):
        return 0 # as soon as possible!


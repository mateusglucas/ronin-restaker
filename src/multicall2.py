from web3 import Web3
from eth_abi import encode_single, decode_single
import utils
import os

#  Observações:
#     _encode_transaction_data poderia ser obtido por call._encode_transaction_data(),
#     mas é um método "privado"

class Multicall2:
    def __init__(self, eth, address):
        self.eth = eth
        self.address = Web3.toChecksumAddress(address)

        with open(os.path.join(os.path.dirname(__file__), 'abi', 'multicall2_abi.json')) as f:
            self.contract = eth.contract(address = self.address, abi = f.read())
    
    @staticmethod
    def _encode_transaction_data(call):
        selector = utils.get_selector(call)
        data = encode_single(utils.get_input_signature(call), call.args)
        return selector + data

    @staticmethod
    def _encode_aggregate_data(calls):
        return [[call.address, Multicall2._encode_transaction_data(call)] for call in calls]
    
    def aggregate(self, calls):
        enc_data = Multicall2._encode_aggregate_data(calls)
        return Multicall2.DecodedAggregate(self.contract.functions.aggregate(enc_data), calls)

    class DecodedAggregate:
        def __init__(self, func, calls):
            self.func = func
            self.calls = calls

        def _decode_aggregate_result(self, result):
            encoded_result = result[1]
            decoded_result = [decode_single(utils.get_output_signature(call), data) for data, call in zip(encoded_result, self.calls)]
            decoded_result = [result[0] if len(result)==1 else result for result in decoded_result]
            return [result[0], decoded_result]

        def call(self, *args, **kwargs):
            return self._decode_aggregate_result(self.func.call(*args, **kwargs))

        



    

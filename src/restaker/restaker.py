from web3 import Web3
from web3.middleware import geth_poa_middleware
from time import sleep
import utils
from multicall2 import Multicall2
import requests
import os

class Restaker:
    _headers ={'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:95.0) Gecko/20100101 Firefox/95.0',
              'content-type': 'application/json'}

    _ronin_rpc = 'https://api.roninchain.com/rpc'
    _free_gas_rpc = 'https://proxy.roninchain.com/free-gas-rpc'
    _multicall2_addr = Web3.toChecksumAddress('0xc76d0d0d3aa608190f78db02bf2f5aef374fc0b9')
    _staking_manager_addr = Web3.toChecksumAddress('0x8bd81a19420bad681b7bfc20e703ebd8e253782d')
    _wron_token_addr = Web3.toChecksumAddress('0xe514d9deb7966c8be0ca922de8a064264ea6bcd4')
    _katana_router_addr = Web3.toChecksumAddress('0x7d0556d55ca1a92708681e2e231733ebd922597d')

    def __init__(self, priv_key, staking_pool_addr):
        self._create_chains()
        self._create_wallet(priv_key)
        self._create_contracts(staking_pool_addr)
        self._get_tokens_decimals_and_symbols()
    
    def _create_chains(self):
        self.ronin_chain = Restaker._create_chain(Restaker._ronin_rpc)
        self.free_gas_chain = Restaker._create_chain(Restaker._free_gas_rpc)

    @staticmethod
    def _create_chain(rpc):
        chain = Web3(Web3.HTTPProvider(rpc, request_kwargs = {'headers':Restaker._headers}))
        chain.middleware_onion.inject(geth_poa_middleware, layer=0)
        return chain
    
    def _create_wallet(self, priv_key):
        self.wallet = self.ronin_chain.eth.account.privateKeyToAccount(priv_key)

    def _create_contracts(self, staking_pool_addr):
        self.multicall2 = Multicall2(self.ronin_chain.eth, Restaker._multicall2_addr)
        self.staking_manager = self._create_contract(Restaker._staking_manager_addr, 'erc20_staking_manager_abi.json')
        self.staking_pool = self._create_contract(staking_pool_addr, 'erc20_staking_pool_abi.json')
        self.wron_token = self._create_contract(Restaker._wron_token_addr, 'wron_abi.json')

        r = self.multicall2.aggregate([
                    self.staking_pool.functions.getStakingToken(),
                    self.staking_pool.functions.getRewardToken()]).call()
        staking_token_addr = Web3.toChecksumAddress(r[1][0])
        reward_token_addr = Web3.toChecksumAddress(r[1][1])

        staking_token_abi = 'katana_pair_abi.json' if self._is_staking_token_lp_token() else 'wron_abi.json'
        self.staking_token = self._create_contract(staking_token_addr, staking_token_abi)
        self.reward_token = self._create_contract(reward_token_addr, 'wron_abi.json')

        if self._is_staking_token_lp_token():
            self.katana_router = self._create_contract(Restaker._katana_router_addr, 'katana_router_abi.json')

            r = self.multicall2.aggregate([
                        self.staking_token.functions.token0(),
                        self.staking_token.functions.token1()]).call()
            token0_addr = Web3.toChecksumAddress(r[1][0])
            token1_addr = Web3.toChecksumAddress(r[1][1])

            # one of them is not wron, but we can use the same abi
            self.token0 = self._create_contract(token0_addr, 'wron_abi.json')
            self.token1 = self._create_contract(token1_addr, 'wron_abi.json')
            
            assert reward_token_addr == Restaker._wron_token_addr, 'Reward token is not WRON!'
            assert Restaker._wron_token_addr == token0_addr or Restaker._wron_token_addr == token1_addr, 'WRON is not in the token pair!'    

    def _create_contract(self, address, abi_file = None):
        if abi_file is None:
            abi = utils.get_contract_abi(address)
        else:
            with open(os.path.join(os.path.dirname(__file__), '..', 'abi', abi_file)) as f:
                abi = f.read()

        return self.ronin_chain.eth.contract(address = address, abi = abi)

    @classmethod
    def _is_staking_token_lp_token(cls):
        raise NotImplementedError('loop not implemented')  

    def _get_tokens_decimals_and_symbols(self):
        r = self.multicall2.aggregate([
                self.staking_pool.functions.getStakingToken(),
                self.staking_pool.functions.getRewardToken()]).call()
        staking_token_addr = Web3.toChecksumAddress(r[1][0])
        reward_token_addr = Web3.toChecksumAddress(r[1][1])

        # only to call decimals() and symbol(). WRON contract will be enough.
        staking_token = self._create_contract(staking_token_addr, 'wron_abi.json')
        reward_token = self._create_contract(reward_token_addr, 'wron_abi.json')

        r = self.multicall2.aggregate([staking_token.functions.symbol(),
                                       staking_token.functions.decimals(),
                                       reward_token.functions.symbol(),
                                       reward_token.functions.decimals(),
                                       self.wron_token.functions.decimals()]).call()
        self.staking_token_symbol = r[1][0]
        self.staking_token_decimals = r[1][1]
        self.reward_token_symbol = r[1][2]
        self.reward_token_decimals = r[1][3]
        self.wron_token_decimals = r[1][4]

    def _get_tokens_prices_usd(self):
        addresses = [self.reward_token.address, self.wron_token.address]

        if self._is_staking_token_lp_token():
            addresses.append(self.token0.address)
            addresses.append(self.token1.address)
        else:
            addresses.append(self.staking_token.address)

        params = {'contract_addresses': ','.join(addresses),
        'vs_currencies': 'usd'}

        r = requests.get('https://api.coingecko.com/api/v3/simple/token_price/{}'.format('ronin'), params=params)
        r.raise_for_status()

        wron_token_price = r.json()[self.wron_token.address.lower()]['usd']
        reward_token_price = r.json()[self.reward_token.address.lower()]['usd']

        if self._is_staking_token_lp_token():
            r_aux = self.multicall2.aggregate([
                self.staking_token.functions.totalSupply(),
                self.staking_token.functions.getReserves(),
                self.token0.functions.decimals(),
                self.token1.functions.decimals(),]).call()
            staking_token_total_supply = r_aux[1][0]
            reserves0, reserves1 = r_aux[1][1][:2]
            token0_decimals = r_aux[1][2]
            token1_decimals = r_aux[1][3]

            token0_price = r.json()[self.token0.address.lower()]['usd'] 
            token1_price = r.json()[self.token1.address.lower()]['usd']
            staking_token_price = (reserves0*token0_price*10**(-token0_decimals)
                                    +reserves1*token1_price*10**(-token1_decimals))/(staking_token_total_supply*10**(-self.staking_token_decimals))
        else:
            staking_token_price = r.json()[self.staking_token.address.lower()]['usd']

        return staking_token_price, reward_token_price, wron_token_price

    def _estimate_gas_to_restake(self):
        raise NotImplementedError('loop not implemented')    
        
    def _get_gain_rate(self, block_number, reward_staking_price_ratio, N = 28800):
        # block time is ~3 now, but it can change in the future.
        # estimate gain rate using the last 28800 blocks (~1 day now)

        gain_rate = self._estimate_gain_rate(block_number - N, block_number, reward_staking_price_ratio)
        return gain_rate
    
    def _estimate_gain_rate(self, from_block, to_block, reward_staking_price_ratio):
        t = self.ronin_chain.eth.get_block(to_block)['timestamp'] - self.ronin_chain.eth.get_block(from_block)['timestamp']

        r = self.multicall2.aggregate([
                self.staking_manager.functions.getIntervalRewards(self.staking_pool.address, from_block, to_block),
                self.staking_pool.functions.getStakingTotal()]).call()
        total_reward = r[1][0]*10**(-self.reward_token_decimals)
        total_staking = r[1][1]*10**(-self.staking_token_decimals)
        
        gain_rate = total_reward/total_staking*reward_staking_price_ratio/t # gain per second

        return gain_rate

    def _restake(self):
        raise NotImplementedError('restaking not implemented') 
    
    @staticmethod
    def _get_log_from_receipt(txn_receipt, event):
        # TODO: o processReceipt retorna logs do mesmo evento, mas nem sempre originados do
        # mesmo endereço. Abrir pull request no GitHub
        logs = event.processReceipt(txn_receipt)
        logs = [log for log in logs if log.address == event.address]
        if len(logs) < 1:
            raise Exception('no log found')
        elif len(logs) > 1:
            raise Exception('more than one log found')
        return logs[0]
    
    def _send_signed_transaction(self, call, params={}):
        free_gas_req = self.free_gas_chain.provider.make_request('eth_getFreeGasRequests',[self.wallet.address])['result']

        params['gasPrice'] = Web3.toWei('0', 'gwei') if free_gas_req>0 else self.ronin_chain.eth.gas_price
        params['nonce'] = self.ronin_chain.eth.getTransactionCount(self.wallet.address)
        params['from'] = self.wallet.address

        txn = call.build_transaction(params)
        
        # Gas estimate, as described in Eth.send_transaction(transaction):
        #
        # If the transaction specifies a data value but does not specify gas then the gas 
        # value will be populated using the estimate_gas() function with an additional buffer 
        # of 100000 gas up to the gasLimit of the latest block. In the event that the value 
        # returned by estimate_gas() method is greater than the gasLimit a ValueError will be 
        # raised.
        gas_limit = self.ronin_chain.eth.get_block('latest').gasLimit

        if txn['gas'] > gas_limit:
            raise Exception('Estimated gas greater than last block limit')

        txn['gas'] = min(txn['gas'] + 100000, gas_limit)

        signed_txn = self.wallet.sign_transaction(txn)
        txn_hash = self.free_gas_chain.eth.send_raw_transaction(signed_txn.rawTransaction)
        
        return txn_hash

    def _wait_txn_receipt(self, txn_hash):
        timeouts = [3]*5 + [10]*5 + [60]*5 + [5*60]
        time_idx = 0
        while True:
            sleep(timeouts[time_idx])
            if time_idx < len(timeouts)-1:
                time_idx += 1
            try:
                return self.free_gas_chain.eth.get_transaction_receipt(txn_hash)
            except:
                pass

        raise Exception('can not get transaction receipt')
    

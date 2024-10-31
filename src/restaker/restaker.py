from web3 import Web3
from web3.middleware import geth_poa_middleware
from time import sleep
import utils
from multicall2 import Multicall2
import requests
import os
from filelock import FileLock

class Restaker:
    _headers ={'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:95.0) Gecko/20100101 Firefox/95.0',
              'content-type': 'application/json'}

    _ronin_rpc = 'https://api.roninchain.com/rpc'
    _free_gas_rpc = 'https://proxy.roninchain.com/free-gas-rpc'
    _multicall2_addr = Web3.to_checksum_address('0xc76d0d0d3aa608190f78db02bf2f5aef374fc0b9')
    _staking_manager_addr = Web3.to_checksum_address('0x8bd81a19420bad681b7bfc20e703ebd8e253782d')
    _wron_token_addr = Web3.to_checksum_address('0xe514d9deb7966c8be0ca922de8a064264ea6bcd4')
    _permissioned_router_addr = Web3.to_checksum_address('0xc05afc8c9353c1dd5f872eccfacd60fd5a2a9ac7')

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
        self.wallet = self.ronin_chain.eth.account.from_key(priv_key)

    def _create_contracts(self, staking_pool_addr):
        self.multicall2 = Multicall2(self.ronin_chain.eth, Restaker._multicall2_addr)
        self.staking_manager = self._create_contract(Restaker._staking_manager_addr, 'erc20_staking_manager_abi.json')
        self.staking_pool = self._create_contract(staking_pool_addr, 'erc20_staking_pool_abi.json')
        self.wron_token = self._create_contract(Restaker._wron_token_addr, 'wron_abi.json')

        r = self.multicall2.aggregate([
                    self.staking_pool.functions.getStakingToken(),
                    self.staking_pool.functions.getRewardToken()]).call()
        staking_token_addr = Web3.to_checksum_address(r[1][0])
        reward_token_addr = Web3.to_checksum_address(r[1][1])

        staking_token_abi = 'katana_pair_abi.json' if self._is_staking_token_lp_token() else 'wron_abi.json'
        self.staking_token = self._create_contract(staking_token_addr, staking_token_abi)
        self.reward_token = self._create_contract(reward_token_addr, 'wron_abi.json')

        if self._is_staking_token_lp_token():
            self.permissioned_router = self._create_contract(Restaker._permissioned_router_addr, 'permissioned_router_abi.json')

            r = self.multicall2.aggregate([
                        self.staking_token.functions.token0(),
                        self.staking_token.functions.token1()]).call()
            token0_addr = Web3.to_checksum_address(r[1][0])
            token1_addr = Web3.to_checksum_address(r[1][1])

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
        raise NotImplementedError('not implemented')  

    def _get_tokens_decimals_and_symbols(self):
        r = self.multicall2.aggregate([
                self.staking_pool.functions.getStakingToken(),
                self.staking_pool.functions.getRewardToken()]).call()
        staking_token_addr = Web3.to_checksum_address(r[1][0])
        reward_token_addr = Web3.to_checksum_address(r[1][1])

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

    def _get_tokens_prices_usd_from_liquidity_pools(self):
        wron_usdc_lp_staking_pool_addr = Web3.to_checksum_address('0xba1c32baff8f23252259a641fd5ca0bd211d4f65')
        wron_axs_lp_staking_pool_addr = Web3.to_checksum_address('0x14327fa6a4027d8f08c0a1b7feddd178156e9527')
        wron_weth_lp_staking_pool_addr = Web3.to_checksum_address('0xb9072cec557528f81dd25dc474d4d69564956e1e')
        wron_slp_lp_staking_pool_addr = Web3.to_checksum_address('0x4e2d6466a53444248272b913c105e9281ec266d8')

        staking_pools_addr = [wron_usdc_lp_staking_pool_addr, 
                              wron_axs_lp_staking_pool_addr, 
                              wron_weth_lp_staking_pool_addr,
                              wron_slp_lp_staking_pool_addr]

        staking_pools = [self._create_contract(addr, 'erc20_staking_pool_abi.json') for addr in staking_pools_addr]

        r = self.multicall2.aggregate([staking_pool.functions.getStakingToken() for staking_pool in staking_pools]).call()
        lp_tokens = [self._create_contract(Web3.to_checksum_address(addr), 'katana_pair_abi.json') for addr in r[1]]

        r = self.multicall2.aggregate([lp_token.functions.getReserves() for lp_token in lp_tokens] + 
                                      [lp_token.functions.token0() for lp_token in lp_tokens] + 
                                      [lp_token.functions.token1() for lp_token in lp_tokens]).call()
        
        n_tokens = len(lp_tokens)
        reserves = r[1][:n_tokens]
        token0_addr = r[1][n_tokens:2*n_tokens]
        token1_addr = r[1][2*n_tokens:]

        token0 = [self._create_contract(Web3.to_checksum_address(addr), 'wron_abi.json') for addr in token0_addr] 
        token1 = [self._create_contract(Web3.to_checksum_address(addr), 'wron_abi.json') for addr in token1_addr]

        r = self.multicall2.aggregate([token.functions.symbol() for token in token0 + token1] + 
                                      [token.functions.decimals() for token in token0 + token1]).call()
        token0_symbols = r[1][:n_tokens]
        token1_symbols = r[1][n_tokens:2*n_tokens]
        token0_decimals = r[1][2*n_tokens:3*n_tokens]
        token1_decimals = r[1][3*n_tokens:]

        reserves_dict = {}

        for token0_sym, token1_sym, token0_dec, token1_dec, [token0_reserve, token1_reserve, _] in zip(token0_symbols, token1_symbols, token0_decimals, token1_decimals, reserves):
            if token0_sym in reserves_dict and token1_sym in reserves_dict:
                raise Exception("Both tokens are already in reserves dict.")
            
            if token0_sym in reserves_dict:
                reserves_dict[token1_sym] = token1_reserve * 10**(-token1_dec) * reserves_dict[token0_sym]/(token0_reserve*10**(-token0_dec))
            elif token1_sym in reserves_dict:
                reserves_dict[token0_sym] = token0_reserve * 10**(-token0_dec) * reserves_dict[token1_sym]/(token1_reserve*10**(-token1_dec))
            else:
                reserves_dict[token0_sym] = token0_reserve * 10**(-token0_dec)
                reserves_dict[token1_sym] = token1_reserve * 10**(-token1_dec)

        prices_dict = {}
        for key in reserves_dict:
            prices_dict[key] = reserves_dict['USDC']/reserves_dict[key]

        return prices_dict

    def _get_tokens_prices_usd(self):
        r = requests.get('https://exchange-rate.skymavis.com/')
        r.raise_for_status()
        r = r.json()
    
        if self._is_staking_token_lp_token():
            r_aux = self.multicall2.aggregate([self.reward_token.functions.symbol(),
                                           self.wron_token.functions.symbol(),
                                           self.token0.functions.symbol(),
                                           self.token1.functions.symbol(),
                                           self.staking_token.functions.totalSupply(),
                                           self.staking_token.functions.getReserves(),
                                           self.token0.functions.decimals(),
                                           self.token1.functions.decimals()]).call()
            
            reward_token_symbol = r_aux[1][0]
            wron_token_symbol = r_aux[1][1]
            token0_symbol = r_aux[1][2]
            token1_symbol = r_aux[1][3]
            staking_token_total_supply = r_aux[1][4]
            reserves0, reserves1 = r_aux[1][5][:2]
            token0_decimals = r_aux[1][6]
            token1_decimals = r_aux[1][7]

            token0_price = r[token0_symbol.lower()]['usd'] 
            token1_price = r[token1_symbol.lower()]['usd']
            staking_token_price = (reserves0*token0_price*10**(-token0_decimals)
                                    +reserves1*token1_price*10**(-token1_decimals))/(staking_token_total_supply*10**(-self.staking_token_decimals))
        else:
            r_aux = self.multicall2.aggregate([self.reward_token.functions.symbol(),
                                           self.wron_token.functions.symbol(),
                                           self.staking_token.functions.symbol()]).call()
            
            reward_token_symbol = r_aux[1][0]
            wron_token_symbol = r_aux[1][1]
            staking_token_symbol = r_aux[1][2]

            staking_token_price = r[staking_token_symbol.lower()]['usd']

        wron_token_price = r[wron_token_symbol.lower()]['usd']
        reward_token_price = r[reward_token_symbol.lower()]['usd']

        return staking_token_price, reward_token_price, wron_token_price

    def _estimate_gas_to_restake(self):
        raise NotImplementedError('not implemented')    
        
    def _get_gain_rate(self, reward_staking_price_ratio, N = 28800):
        # block time is ~3 now, but it can change in the future.
        # estimate gain rate using the last 28800 blocks (~1 day now)
        to_block = self.ronin_chain.eth.block_number
        from_block = to_block - N

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
        logs = event.process_receipt(txn_receipt)
        logs = [log for log in logs if log.address == event.address]
        if len(logs) < 1:
            raise Exception('no log found')
        elif len(logs) > 1:
            raise Exception('more than one log found')
        return logs[0]
    
    def _send_signed_transaction(self, call, params={}):
        with FileLock(os.path.join(os.path.dirname(__file__), self.wallet.address + '.lock')):
            params['gasPrice'] = self.ronin_chain.eth.gas_price
            params['nonce'] = self.ronin_chain.eth.get_transaction_count(self.wallet.address, block_identifier = 'pending')
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
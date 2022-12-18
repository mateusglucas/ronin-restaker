import keyring
from web3 import Web3
from web3.middleware import geth_poa_middleware
from time import time, sleep
from staking_abi import staking_contracts_abi, staking_manager_abi
import requests

def print_log(msg, file = 'log.txt'):
    with open(file, 'a') as f:
        msg = '{} - {}'.format(round(time()), msg)
        print(msg)
        print(msg, file=f)

print_log('##### AXS Auto-staker #####')

key = keyring.get_password('ronin','priv_key')

ronin_rpc = 'https://api.roninchain.com/rpc'
free_gas_rpc = 'https://proxy.roninchain.com/free-gas-rpc'

headers ={'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:95.0) Gecko/20100101 Firefox/95.0',
          'content-type': 'application/json'}

ronin_chain = Web3(Web3.HTTPProvider(ronin_rpc, request_kwargs = {'headers':headers}))
ronin_chain.middleware_onion.inject(geth_poa_middleware, layer=0)

free_gas_chain = Web3(Web3.HTTPProvider(free_gas_rpc, request_kwargs = {'headers':headers}))
free_gas_chain.middleware_onion.inject(geth_poa_middleware, layer=0)

account = ronin_chain.eth.account.privateKeyToAccount(key)
ronin_wallet = Web3.toChecksumAddress(account.address)

axs_staking_pool_contract_addr = Web3.toChecksumAddress('0x05b0bb3c1c320b280501b86706c3551995bc8571')
axs_staking_pool_contract = ronin_chain.eth.contract(address = axs_staking_pool_contract_addr, abi=staking_contracts_abi)

staking_manager_contract_addr = Web3.toChecksumAddress('0x8bd81a19420bad681b7bfc20e703ebd8e253782d')
staking_manager_contract = ronin_chain.eth.contract(address = staking_manager_contract_addr, abi=staking_manager_abi)

# array with waiting times, in seconds, for retries when transaction fails
new_try_wait = [5, 5, 60, 60, 60, 60, 60, 5*60, 5*60, 10*60, 3600, 6*3600, 12*3600]
        
tries = 0

state = 0 # state variable: 0-> wait and restake
          #                 1-> verify restake transaction

while True:
    try:
        if state==0:
            claim_block_interval = staking_manager_contract.functions.minClaimedBlocks().call()
            last_claimed_block = staking_manager_contract.functions.userRewardInfo(axs_staking_pool_contract_addr, ronin_wallet).call()[2]

            next_claim_block = claim_block_interval+last_claimed_block
            
            print_log('Next claim on block {}'.format(next_claim_block))

            last_block = ronin_chain.eth.get_block('latest')['number']

            print_log('Actual block: {}'.format(last_block))

            while last_block<next_claim_block:
                time_to_next_claim = (next_claim_block-last_block)*3 # 3 segundos por bloco
                sleep(time_to_next_claim)

                last_block = ronin_chain.eth.get_block('latest')['number']

            free_gas_req = requests.post(url = free_gas_rpc, headers = headers,
                                         json = {"id":2,"jsonrpc":"2.0",
                                                 "method":"eth_getFreeGasRequests",
                                                 "params":[ronin_wallet]}).json()['result']
                                                 
            tx = axs_staking_pool_contract.functions.restakeRewards().buildTransaction({
                                    'from': ronin_wallet,
                                    'chainId': ronin_chain.eth.chain_id,
                                    'nonce': ronin_chain.eth.getTransactionCount(ronin_wallet),
                                    'gasPrice': Web3.toWei('0', 'gwei') if free_gas_req>0 else ronin_chain.eth.gasPrice})
                                    
            # Gas estimate, as described in Eth.send_transaction(transaction):
            #
            # If the transaction specifies a data value but does not specify gas then the gas 
            # value will be populated using the estimate_gas() function with an additional buffer 
            # of 100000 gas up to the gasLimit of the latest block. In the event that the value 
            # returned by estimate_gas() method is greater than the gasLimit a ValueError will be 
            # raised.
            estimGas = tx['gas']
            gasLimit = ronin_chain.eth.get_block('latest').gasLimit

            if estimGas>gasLimit:
                raise Exception('Estimated gas greater than last block limit')

            tx['gas'] = min(estimGas + 100000, gasLimit)
            
            signed_tx = account.sign_transaction(tx)

            txn_hash = free_gas_chain.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            sleep(20*3) # wait for transaction to be processed (margin of 20 blocks)
            
            tries = 0
            state = 1
            
        elif state==1:
                    
            txn_rec = free_gas_chain.eth.get_transaction_receipt(txn_hash)
            
            gas_used = txn_rec['gasUsed']
            gas_price = tx['gasPrice'] # alternative to txn_rec['effectiveGasPrice']
                                       # for some reason, the key effectiveGasPrice 
                                       # is not always returned
            
            print_log('Fee {} RON.'.format(gas_price*gas_used*1e-18))
            
            if txn_rec['status']==0 :
                print_log('Transaction failed!')
            else:
                log = [l for l in txn_rec['logs'] if l['topics'][0]==Web3.keccak(b'Staked(address,address,uint256)')][0]
                qty = log['topics'][3].hex()
                qty = int(qty, base=16)*1e-18
                print_log('Restaked {} AXS.'.format(qty))

            tries = 0
            state = 0
            
    except Exception as e:
        wait_time = new_try_wait[tries] if tries<len(new_try_wait) else new_try_wait[-1]
        tries = tries+1
        
        print_log('Error: {}'.format(e))
        
        # abor transaction verification after 10 tries
        if state==1 and tries>=10:
            print_log('Aborting transaction verification...')
            tries = 0
            state = 0
        else:
            print_log('Next try ({}) in {} s'.format(tries, wait_time))
        
        sleep(wait_time)


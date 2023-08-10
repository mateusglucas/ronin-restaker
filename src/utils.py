from web3 import Web3
import requests
from statistics import median

# Tenta recuperar abi de contrato por API utilizada pelo Ronin Explorer
# Não funciona para o USDC token
def get_contract_abi(contract_addr):
    
    url = 'https://explorer-kintsugi.roninchain.com/v2/2020/contract/{}'.format(contract_addr.lower())
    
    headers ={'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:95.0) Gecko/20100101 Firefox/95.0',
              'content-type': 'application/json'}
    
    r = requests.get(url, headers = headers)
    r.raise_for_status()

    is_proxy = r.json()['result']['is_proxy']
    if is_proxy:
        proxy_addr = r.json()['result']['proxy_to']
        return get_contract_abi(proxy_addr)
    else:
        r = requests.get(url + '/abi', headers = headers)
        r.raise_for_status()
        return r.json()['result']['output']['abi']

def get_function_abi(func):
    # for bounded functions, the abi is already speficied
    if 'abi' in func.__dict__ and func.abi is not None:
        return func.abi
    
    # for unbounded functions, the abi isn't specified yet because
    # we can have function overloading.
    # the abi will be recovered only if the function isn't overloaded
    # in the contract.
    contract = func.contract_abi
    f_abi = [f for f in contract if 'name' in f.keys() and f['name'] == func.fn_name]
    if len(f_abi) > 1:
        raise Exception('contract with more than one function with the same name')
    if len(f_abi) < 1:
        raise Exception('function name not fount in the contract abi')    
    return f_abi[0]

def get_input_signature(func):
    abi = get_function_abi(func)
    input_signature = [fin['type'] for fin in abi['inputs']]
    return input_signature

def get_output_signature(func):
    abi = get_function_abi(func)
    output_signature = [fout['type'] for fout in abi['outputs']]
    return output_signature

def get_selector(func):  
    # for bounded functions, the selector is already speficied
    if 'selector' in func.__dict__ and func.selector is not None:
        return bytes.fromhex(func.selector[2:])
    
    # for unbounded functions, the selector isn't specified yet because
    # we can have function overloading.
    # the selector will be recovered only if the function isn't overloaded
    # in the contract.
    input_signature = get_input_signature(func)
    input_signature = ','.join(input_signature)
    input_signature = '({})'.format(input_signature)
    return Web3.keccak(text = func.fn_name + input_signature)[:4]

def get_last_txns_from_explorer(func, N = 10, only_success = False):
    headers ={'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:95.0) Gecko/20100101 Firefox/95.0',
              'content-type': 'application/json'}
    
    size = 100
    start_idx = 0
    info = []
    hashes = set()

    url = 'https://explorerv3-api.roninchain.com/txs/{}'.format(func.address.lower())

    while len(info)<N:
        req = requests.get(url, headers = headers, params={'from': start_idx, 'size': size})
        req.raise_for_status()

        req = req.json()['results']
        if(len(req) != size):
            raise Exception('Results with less items than expected: got {}, expected {}'.format(len(req), size))
        
        temp = [r for r in req if r['input'][:10] == get_selector(func).hex() and r['hash'] not in hashes]
        if only_success == True:
            temp = [t for t in temp if t['status']==1]

        hashes.update([t['hash'] for t in temp])
        start_idx += size
        info += temp

    return info[:N]

def get_gas_used_from_explorer(func, N=10):
    txns = get_last_txns_from_explorer(func = func, N = N, only_success = True)
    return [int(tx['gas_used']) for tx in txns]

def estimate_gas_used(func, N=10):
    values = get_gas_used_from_explorer(func = func, N = N)
    return round(median(values))
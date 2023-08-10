from web3 import Web3
import keyring
from restaker import KatanaRestaker, AXSRestaker
from strategy import OptimalIntervalStrategy, ASAPStrategy
from pwinput import pwinput

if __name__ == '__main__':
    wron_usdc_lp_staking_pool_addr = Web3.toChecksumAddress('0xba1c32baff8f23252259a641fd5ca0bd211d4f65')
    wron_axs_lp_staking_pool_addr = Web3.toChecksumAddress('0x14327fa6a4027d8f08c0a1b7feddd178156e9527')
    wron_weth_lp_staking_pool_addr = Web3.toChecksumAddress('0xb9072cec557528f81dd25dc474d4d69564956e1e')
    wron_slp_lp_staking_pool_addr = Web3.toChecksumAddress('0x4e2d6466a53444248272b913c105e9281ec266d8')

    katana_pools = [wron_usdc_lp_staking_pool_addr,
                    wron_axs_lp_staking_pool_addr,
                    wron_weth_lp_staking_pool_addr,
                    wron_slp_lp_staking_pool_addr]
    
    is_first_iter = True 
    while is_first_iter or option not in ['y', 'n']:   
        if not is_first_iter:
            print('Incorect option. Try again!')
        is_first_iter = False
        option = input('Do you want to set your private key? [y/N] : ').lower()
        option = 'n' if option == '' else option

    if option == 'y':
        keyring.set_password('ronin','priv_key', pwinput(prompt='Ronin wallet private key (0x... format): ', mask='*'))
        print('Private key stored.')

    print('')
    print('Select the desired staking pool:')
    print('')
    print('1) WRON-USDC')
    print('2) WRON-AXS')
    print('3) WRON-WETH')
    print('4) WRON-SLP')
    print('5) AXS')
    print('')

    is_first_iter = True
    while is_first_iter or desired_pool not in [1, 2, 3, 4, 5]:
        if not is_first_iter:
            print('Incorrect option. Try again!')
        is_first_iter = False
        desired_pool = int(input('Desired staking pool: '))

    if desired_pool in [1,2,3,4]:
        restaker = KatanaRestaker(keyring.get_password('ronin','priv_key'), katana_pools[desired_pool - 1])
    elif desired_pool == 5:
        restaker = AXSRestaker(keyring.get_password('ronin','priv_key'))
    else:
        raise Exception('unexpected option value {}'.format(desired_pool))
    
    print('')
    print('Select desired strategy:')
    print('')
    print('1) ASAP (as soon as possible)')
    print('2) Optimal interval (maximize compound interest)')
    print('')

    is_first_iter = True
    while is_first_iter or desired_strat not in [1, 2]:
        if not is_first_iter:
            print('Incorrect option. Try again!')
        is_first_iter = False
        desired_strat = int(input('Desired strategy: '))

    if desired_strat == 1:
        strat = ASAPStrategy(restaker)
    elif desired_strat == 2:
        default_min_ron_balance = 1
        desired_min_ron_balance = input('Desired min RON balance (leave blank to use default value {}): '.format(default_min_ron_balance))
        desired_min_ron_balance = default_min_ron_balance if desired_min_ron_balance == '' else int(desired_min_ron_balance)
        strat = OptimalIntervalStrategy(restaker, desired_min_ron_balance)
    else:
        raise Exception('unexpected option value {}'.format(desired_pool))
     
    strat.run()

# # staking pools com recompensas
# wron_usdc_lp_staking_pool_addr = Web3.toChecksumAddress('0xba1c32baff8f23252259a641fd5ca0bd211d4f65')
# wron_axs_lp_staking_pool_addr = Web3.toChecksumAddress('0x14327fa6a4027d8f08c0a1b7feddd178156e9527')
# wron_weth_lp_staking_pool_addr = Web3.toChecksumAddress('0xb9072cec557528f81dd25dc474d4d69564956e1e')
# wron_slp_lp_staking_pool_addr = Web3.toChecksumAddress('0x4e2d6466a53444248272b913c105e9281ec266d8')

# strat = OptimalIntervalStrategy(restaker, 1)
# strat.run()

# #staking pools sem recompensas
# slp_weth_lp_staking_pool_addr = Web3.toChecksumAddress('0xd4640c26c1a31cd632d8ae1a96fe5ac135d1eb52')
# axs_weth_lp_staking_pool_addr = Web3.toChecksumAddress('0x487671acdea3745b6dac3ae8d1757b44a04bfe8a')

# # Liquidity pool tokens
# ron_usdc_lp_token_addr = Web3.toChecksumAddress('0x4f7687affc10857fccd0938ecda0947de7ad3812')
# ron_weth_lp_token_addr = Web3.toChecksumAddress('0x2ecb08f87f075b5769fe543d0e52e40140575ea7')
# ron_slp_lp_token_addr = Web3.toChecksumAddress('0x8f1c5eda143fa3d1bea8b4e92f33562014d30e0d')
# ron_axs_lp_token_addr = Web3.toChecksumAddress('0x32d1dbb6a4275133cc49f1c61653be3998ada4ff')
# usdc_weth_lp_token_addr = Web3.toChecksumAddress('0xa7964991f339668107e2b6a6f6b8e8b74aa9d017')
# slp_weth_lp_token_addr = Web3.toChecksumAddress('0x306a28279d04a47468ed83d55088d0dcd1369294')
# axs_weth_lp_token_addr = Web3.toChecksumAddress('0xc6344bc1604fcab1a5aad712d766796e2b7a70b9')
# #slp_axs_lp_token_addr ????
# #slp_usdc_lp_token_addr - usdc <-> wron/weth <->slp
# #axs_usdc_lp_token_addr - axs <-> wron/weth <->usdc

# # endereços suspeitos em que é chamada a função getReserves() via Multicall2 no Katana Interface quando
# # se coloca para fazer swap entre AXS e SLP, no momento de cálculo da quantidade de SLP
# # 0x52022808db40a5077da5875c140375470cc181b3
# # 0xec087b4defcf76d5666ef366d7ae98cf926ae545
# # 0x572bca391432053cded92926d429e02a079c914e

# # Tokens
# wron_token_addr = Web3.toChecksumAddress('0xe514d9deb7966c8be0ca922de8a064264ea6bcd4')
# slp_token_addr = Web3.toChecksumAddress('0xa8754b9fa15fc18bb59458815510e40a12cd2014')
# axs_token_addr = Web3.toChecksumAddress('0x97a9107c1793bc407d6f527b77e7fff4d812bece')
# usdc_token_addr = Web3.toChecksumAddress('0x0b7007c13325c48911f73a2dad5fa5dcbf808adc')
# weth_token_addr = Web3.toChecksumAddress('0xc99a6a985ed2cac1ef41640596c5a5f9f4e19ef5')
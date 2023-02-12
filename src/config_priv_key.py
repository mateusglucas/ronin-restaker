import keyring
from pwinput import pwinput

print('##### AXS Auto-staker configuration #####')
print('')
print('ONLY PASTE YOUR PRIVATE KEY BELOW IF YOU KNOW WHAT YOU ARE DOING AND UNDERSTAND ALL THE RISKS INVOLVED!')
print('')
keyring.set_password('ronin','priv_key', pwinput(prompt='Ronin wallet private key: ', mask='*'))

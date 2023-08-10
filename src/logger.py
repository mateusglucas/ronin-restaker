from time import time

class Logger:
    def __init__(self, filename = 'log.txt'):
        self.filename = filename

    def print(self, msg):      
        with open(self.filename, 'a') as f:
            msg = '{} - {}'.format(round(time()), msg)
            print(msg)
            print(msg, file = f)
import random
import string

class _FlowIds:
    def __init__(self):
        self.count = 1 
    def next(self):
        self.count += 1
        return f"FL_{self.count}"
    
class _Utils:
    @staticmethod
    def get_random_id(prefix=''):
        return prefix + '_' + ''.join(random.choices(string.ascii_letters + string.digits, k=8))
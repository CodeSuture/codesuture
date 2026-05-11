from codesuture.debuggee import enable

import time
data = {"user": None}

def get_user_name():
    user = data["user"]          
    return user["name"]          

def calc_discount(price):
    discount = 0
    return price / discount

if __name__ == '__main__':
    enable(5678)
    print(get_user_name())   
    print(calc_discount(100))
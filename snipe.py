import argparse
import time
import json
from web3 import Web3
from datetime import datetime
import threading
import os

from pyuniswap.pyuniswap import Token

print("module import end!")
f = open('config.json')
data = json.load(f)
provider_http = data["provider_http"]
provider_wss = data["provider_wss"]
wallet_address = data["wallet_address"]
private_key = data["private_key"]
new_token = data["new_token_address"]
presale_address = data["presale_address"]
buy_amount = int(data["buy_amount"] * pow(10, 18))
TRAILINGSTOP = int(data["trailing_stop"])
take_profit = float(data["trailing_stop"])
stop_loss = float(data["stop_loss"])
slippage = int(data["slippage"]) / 100
speed = int(data["speed"])
gas_limit = int(data["gas_limit"])
print("variable initialize end")

current_token = Token(
                address=new_token,
                provider=provider_http,
                provider_wss=provider_wss
            )
current_token.connect_wallet(wallet_address, private_key)  # craete token
current_token.set_gas_limit(gas_limit)
print(current_token.is_connected())  # check if the token connected correctlye
buy_price = 0
sell_price = 0
stop_loss_price = 0
token_found = False
token_decimal = current_token.decimals()
print("step1")

token_balance = current_token.balance()
liquidity_add_methods = ['0xf305d719', '0xe8e33700', '0x384e03db', '0x4515cef3', '0x267dd102', '0xe8078d94']
print(f"New_token:{new_token}, buy_amount: {buy_amount}, trailing_stop:{TRAILINGSTOP}, take_profit:{take_profit}, stop_loss{stop_loss}, "
      f"Speed:{speed}, gas_limit:{gas_limit}")

def mempool():
    print('Waiting liquidity to be added')
    event_filter = current_token.web3.eth.filter("pending")
    while not token_found:
        try:
            new_entries = event_filter.get_new_entries()
            threading.Thread(target=get_event, args=(new_entries)).start()
        except Exception as err:
            print(err)
            pass

def get_event( new_entries):
    for event in new_entries[::-1]:
        try:
            threading.Thread(target=handle_event, args=(event)).start()
            if token_found:
                break
        except Exception as e:
            print(e)
            pass

def handle_event(event):
    try:
        transaction = current_token.web3.eth.getTransaction(event)
        if (transaction.input[:10].lower() in liquidity_add_methods and new_token[2:].lower() in transaction.input.lower()):
            threading.Thread(target=buy, args=(int(transaction.gasPrice), int(transaction.gas), )).start()
            token_found = True
            print("Liquidity Added : {}".format(event.hex()))
            print('Start Buy')
    except Exception as e:
        pass

def buy(gas_price, gas_limit):
    current_token.set_gas_limit(gas_limit)
    sign_tx = current_token.buy(int(buy_amount), slippage=slippage,
                                gas_price=int(gas_price*speed), timeout=2100)
    try:
        result = current_token.send_buy_transaction(sign_tx)
        print('Wait until transaction completed...')
        print(f'Buy transaction: {result.hex()}')
        retry = 1
        while retry < 300:
            current_balance = current_token.balance()
            if current_balance > token_balance:
                print("Buy transaction confirmed")
                buy_price = current_token.price(10 ** token_decimal)
                sell_price = buy_price*(10**token_decimal) * take_profit / 100
                stop_loss_price = buy_price*(10**token_decimal) * stop_loss / 100
                print({'buy_price': buy_price})
                # approve
                if not current_token.is_approved(new_token, buy_amount):
                    print(f'Approving: {result.hex()}')
                    current_token.approve(new_token, gas_price=int(gas_price) * 10 ** 9, timeout=2100)
                token_balance = current_token.balance()
                start_sell()

            retry += 1
            time.sleep(1)
        if retry >= 300:
            print("Buy transaction failed")

    except Exception as e:
        print(f'Buy error: {e}')
        print(f'Retry ...')
        print(f'Buy error: {e}')



def start_sell():
    trailing_stop = buy_price * (100 - TRAILINGSTOP) / 100
    print("Trailing stop", trailing_stop)
    print("Buy price", buy_price)
    while True:
        current_price = current_token.price()
        current_trailing_stop = current_price * (100 - TRAILINGSTOP) / 100
        print("current_price: ", current_trailing_stop)
        if current_price > sell_price or current_price < stop_loss_price or (current_price < trailing_stop):
            print("sell with half price")
            sell()
        trailing_stop = current_trailing_stop

def sell():
    global current_token

    balance = current_token.balance()
    sell_flag = False
    while not sell_flag:
        try:
            transaction_addreses = current_token.sell(balance, slippage=slippage, timeout=2100,
                                                      gas_price=int(gas_price) * 10 ** 9)  # sell token as amount
            print("Sell transaction address", transaction_addreses)
            sell_flag = True
        except Exception as e:
            print(e)



def main():
   threading.Thread(target=mempool).start()

if __name__ == '__main__':
    main()

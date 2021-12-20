import ccxt
import config
import schedule
import pandas as pd
pd.set_option('display.max_rows', None)

import warnings
warnings.filterwarnings('ignore')

import numpy as np
from datetime import datetime
import time

exchange = ccxt.binanceusdm({
    "apiKey": config.BINANCE_API_KEY,
    "secret": config.BINANCE_SECRET_KEY,
    "dualSidePosition": true
})

def tr(data):
    data['previous_close'] = data['close'].shift(1)
    data['high-low'] = abs(data['high'] - data['low'])
    data['high-pc'] = abs(data['high'] - data['previous_close'])
    data['low-pc'] = abs(data['low'] - data['previous_close'])

    tr = data[['high-low', 'high-pc', 'low-pc']].max(axis=1)

    return tr

def atr(data, period):
    data['tr'] = tr(data)
    atr = data['tr'].rolling(period).mean()

    return atr

def supertrend(df, period=7, atr_multiplier=3):
    hl2 = (df['high'] + df['low']) / 2
    df['atr'] = atr(df, period)
    df['upperband'] = hl2 + (atr_multiplier * df['atr'])
    df['lowerband'] = hl2 - (atr_multiplier * df['atr'])
    df['in_uptrend'] = True

    for current in range(1, len(df.index)):
        previous = current - 1

        if df['close'][current] > df['upperband'][previous]:
            df['in_uptrend'][current] = True
        elif df['close'][current] < df['lowerband'][previous]:
            df['in_uptrend'][current] = False
        else:
            df['in_uptrend'][current] = df['in_uptrend'][previous]

            if df['in_uptrend'][current] and df['lowerband'][current] < df['lowerband'][previous]:
                df['lowerband'][current] = df['lowerband'][previous]

            if not df['in_uptrend'][current] and df['upperband'][current] > df['upperband'][previous]:
                df['upperband'][current] = df['upperband'][previous]
        
    return df


in_position = False

def check_buy_sell_signals(df):
    global in_position

    print("checking for buy and sell signals")
    print(df.tail(5))
    last_row_index = len(df.index) - 1
    previous_row_index = last_row_index - 1

    if not df['in_uptrend'][previous_row_index] and df['in_uptrend'][last_row_index]:
        print("changed to uptrend, buy")
        if not in_position:
            pair = "ADA/USDT"
            response = exchange.set_leverage(20, 'ADA/USDT')
            print(response)
            position = exchange.fetch_balance()['info']['positions']
            pos = [p for p in position if p['symbol'] == "ETHUSDT"][0]
            close_position = exchange.create_order(symbol=symbol, type="MARKET", side="sell", amount=pos['positionAmt'], params={"reduceOnly": True}) 
            print(close_position)   
            #return exchange.fetch_balance().get(settings.TRADE_FROM).get('free')
            to_use = float(exchange.fetch_balance().get(settings.TRADE_FROM).get('free'))
            price = float(exchange.fetchTicker(pair).get('last'))

            decide_position_to_use = to_use / price
            quantity_to_buy = decide_position_to_use*settings.TRADE_SLIP_RANGE

            order = exchange.createOrder(pair, 'market', 'buy', quantity_to_buy, "positionSide": "LONG")
            print(order)
            # order = exchange.create_market_buy_order('ETH/USD', 0.05)
            # print(order)
            in_position = True
        else:
            print("already in position, nothing to do")
    
    if df['in_uptrend'][previous_row_index] and not df['in_uptrend'][last_row_index]:
        if in_position:
            print("changed to downtrend, sell")
            pair = "ADA/USDT"
            response = exchange.set_leverage(20, 'ADA/USDT')
            print(response)
            position = exchange.fetch_balance()['info']['positions']
            pos = [p for p in position if p['symbol'] == "ETHUSDT"][0]
            close_position = exchange.create_order(symbol=symbol, type="MARKET", side="buy", amount=pos['positionAmt'], params={"reduceOnly": True}) 
            print(close_position)   
            #return exchange.fetch_balance().get(settings.TRADE_FROM).get('free')
            to_use = float(exchange.fetch_balance().get(settings.TRADE_FROM).get('free'))
            price = float(exchange.fetchTicker(pair).get('last'))

            decide_position_to_use = to_use / price
            quantity_to_buy = decide_position_to_use*settings.TRADE_SLIP_RANGE

            order = exchange.createOrder(pair, 'market', 'sell', quantity_to_buy, "positionSide": "SHORT")
            print(order)
            # order = exchange.create_market_sell_order('ETH/USD', 0.05)
            # print(order)
            in_position = False
        else:
            print("You aren't in position, nothing to sell")

def run_bot():
    print(f"Fetching new bars for {datetime.now().isoformat()}")
    bars = exchange.fetch_ohlcv('ADA/USDT', timeframe='1m', limit=100)
    df = pd.DataFrame(bars[:-1], columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

    supertrend_data = supertrend(df)
    
    check_buy_sell_signals(supertrend_data)


schedule.every(10).seconds.do(run_bot)


while True:
    schedule.run_pending()
    time.sleep(1)

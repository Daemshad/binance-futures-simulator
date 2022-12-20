# Binance Futures Realtime Simulator

this project simulates binance futures trading in realtime using binance market data web socket. you can use this in order to test your strategies before trading with real money.

## Usage

install requirements

    pip install -r requirements.txt
 
run server.py and specify symbol, balance and fee rate.

    python server.py --symbol btcusdt --balance 10000 --fee 0.0004

interact with server using client.py

###  import Client and create an instance

    from client import  Client
    
    c  =  Client()

### get last price

    c.get_price()
 
 ### get account info

    c.get_account()

### set leverage

    c.set_leverage(100)
  
### submit market order

    c.submit_order(side='buy',  quantity=2)

### submit limit order

    c.submit_order(side='sell',  quantity=1,  price=16100.0)

### get orders list

    c.get_orders()

### cancel order

    c.cancel_order(id=1)

### get position info

    c.get_position()

### close your position with market price

    c.close_position()

### close your position at limit price

    c.close_position(price=18000.0)

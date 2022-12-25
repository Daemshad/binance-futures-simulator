# Binance Futures Simulator

This project simulates binance futures trading in realtime using binance market data web socket. you can use this in order to test your strategies before trading with real money.

### Features
- Realtime price stream
- Trade in any market (e.g. btcusdt)
- Set your desired balance and fee rate
- Live processing orders with real time prices
- Set leverage on your position
- Submit market and limit orders
- Cancel orders
- Close your position at market or limit price
- Pnl and margin calculations
- Liquidation check for position
- Json file database

## Usage

install requirements

    pip install -r requirements.txt
 
run server.py and specify symbol, balance and fee rate.

    python server.py --symbol btcusdt --balance 10000 --fee 0.0004

interact with server using client.py

###  import Client and create an instance

```python
from client import  Client
    
c  =  Client()
```

### get last price

```python
c.get_price()
```

### get account info

```python
c.get_account()
```

### set leverage

```python
c.set_leverage(100)
```

### submit market order

```python
c.submit_order(side='buy',  quantity=2)
```

### submit limit order

```python
c.submit_order(side='sell',  quantity=1,  price=16100.0)
```

### get orders list

```python
c.get_orders()
```

### cancel order

```python
c.cancel_order(id=1)
```

### get position info

```python
c.get_position()
```

### close your position with market price

```python
c.close_position()
```

### close your position at limit price

```python
c.close_position(price=18000.0)
```

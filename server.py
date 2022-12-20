import argparse
import logging
import datetime
import time
import json
import websocket
from tinydb import TinyDB
from decimal import Decimal
from enum import IntEnum
from itertools import count


class Position:
    def __init__(self):
        self.side = 0  # 1 for Long -1 for Short 0 for None
        self.quantity = Decimal("0.0")
        self.entry_price = Decimal("0.0")
        self.leverage = 1

    def set_leverage(self, leverage: int):
        """
        sets leverage if there is no open position
        """
        if self.side == 0:
            self.leverage = leverage
        return self.leverage

    def increase(self, quantity: Decimal, price: Decimal):
        """
        increases position quantity and adjusts entry price
        """
        assert quantity > 0.0
        assert price > 0.0
        self.entry_price = (self.quantity * self.entry_price + quantity * price) / (self.quantity + quantity)
        self.quantity += quantity
        return True

    def decrease(self, quantity: Decimal, price: Decimal):
        """
        decreases position quantity and returns initial investment plus pnl
        """
        assert 0.0 < quantity <= self.quantity
        assert price > 0.0
        self.quantity -= quantity
        initial = quantity * self.entry_price
        pnl = self.side * quantity * (price - self.entry_price)
        if self.quantity == 0.0:
            # close position
            self.side = 0
            self.entry_price = Decimal("0.0")
        return initial, pnl

    def pnl(self, price: Decimal):
        """
        returns pnl in given price
        """
        return self.side * self.quantity * (price - self.entry_price)

    def margin(self, price: Decimal):
        """
        returns percentage of pnl to initial investment
        if it hits -100 position will get liquidated
        """
        if self.side:
            margin = 100 * self.pnl(price) / (self.quantity * self.entry_price / self.leverage)
            return margin.quantize(Decimal("0.00"))
        return 0.0

    def value(self, price: Decimal, fee_rate: Decimal):
        """
        total position value in qoute asset
        considers fee for closing position
        """
        fee = (self.quantity * self.entry_price + self.pnl(price)) * fee_rate
        value = self.quantity * self.entry_price / self.leverage + self.pnl(price) - fee
        return value

    def liquidation_price(self, fee_rate: Decimal):
        """
        returns liquidation price according to leverage and fee rate
        considers fee in liquidation price calculations
        """
        liquidation_price = self.entry_price - self.side * self.entry_price / self.leverage
        fee = liquidation_price * self.quantity * fee_rate
        liquidation_price += self.side * fee
        return liquidation_price

    def to_dict(self, price: Decimal, fee_rate: Decimal):
        return (
            dict(
                side="Long" if self.side == 1 else "Short" if self.side == -1 else "None",
                quantity=float(self.quantity),
                entry_price=round(float(self.entry_price), 2),
                leverage=self.leverage,
                liquidation_price=round(float(self.liquidation_price(fee_rate)), 2),
                pnl=round(float(self.pnl(price)), 2),
                margin=round(float(self.margin(price)), 2),
            )
            if self.side
            else {}
        )

    def __repr__(self) -> str:
        side = "Long" if self.side == 1 else "Short" if self.side == -1 else "None"
        return f"{side} {round(self.quantity,8)} @ {round(self.entry_price,2)}$"


class Server:
    def __init__(
        self,
        symbol: str,
        balance: int,
        fee_rate: float,
    ):
        # attributes
        self.symbol = symbol.lower()
        self.balance = balance
        self.position = Position()
        self.fee_rate = Decimal(fee_rate).quantize(Decimal("0.0000"))
        self.unit = 1  # (usd) minimum order value
        self.oid_counter = count()
        # websocket
        print("Trying to connect binance ...")
        websocket.enableTrace(False)
        self.ws = websocket.create_connection("wss://fstream.binance.com/ws")
        self.subscribe()
        # database
        self.db = TinyDB("database.json")
        self.db.truncate()
        self.db.insert(
            {
                "time": datetime.datetime.now().strftime("%H:%M:%S"),
                "price": float(self.last_price()),
                "balance": float(balance),
                "value": float(balance),
                "order": {},
                "orders": [],
                "leverage": 1,
                "position": {},
            }
        )
        # logging
        logging.basicConfig(format="%(asctime)s - %(message)s", level=logging.INFO)

    def subscribe(self):
        """
        subscribes to binance tickers socket
        """
        self.ws.send(
            json.dumps(
                {
                    "method": "SUBSCRIBE",
                    "params": [f"{self.symbol.lower()}@miniTicker"],
                    "id": 1,
                }
            )
        )
        self.ws.recv()
        return True

    def unsubscribe(self):
        """
        unsubscribes from binance tickers socket
        """
        self.ws.send(
            json.dumps(
                {
                    "method": "UNSUBSCRIBE",
                    "params": [f"{self.symbol.lower()}@miniTicker"],
                    "id": 1,
                }
            )
        )
        return True

    def last_price(self):
        """
        gets last price from websocket and returns it
        """
        result = self.ws.recv()
        result = json.loads(result)
        price = result.get("c")
        return Decimal(price).quantize(Decimal("0.0"))

    def set_leverage(self):
        """
        gets user leverage from database and set it
        """
        leverage = int(self.db.all()[0]["leverage"])
        return self.position.set_leverage(leverage)

    def submit_order(self):
        """
        gets user order form database and pushs it to orders list
        """
        db = self.db.all()[0]
        if db.get("order"):
            orders = db["orders"]
            db["order"]["id"] = next(self.oid_counter)
            orders.append(db["order"])
            self.db.update(dict(order={}, orders=orders))
            logging.info(f'{db["price"]} - Order submited')
            return True
        return False

    def check_orders(self, orders: list, price: Decimal):
        """
        checks each order in orders list with given price
        returns list of orders to process
        """
        orders_to_process = []
        for order in orders:
            if order.get("price") is None:
                orders_to_process.append(order)
            else:
                order_side = order["side"].upper()
                order_price = Decimal(order["price"])
                if (order_side == "BUY" and order_price >= price) or (order_side == "SELL" and order_price <= price):
                    orders_to_process.append(order)
        return orders_to_process

    def process_orders(self, price: Decimal):
        """
        processes orders list with given price
        returns True if order processed else False
        """
        # get orders from database and check
        orders = self.db.all()[0]["orders"]
        orders_to_process = self.check_orders(orders, price)

        for order in orders_to_process:

            side = order["side"].upper()

            quantity = Decimal(str(order["quantity"]))

            if order.get("price"):  # adjusts price for limit orders
                if (side == "BUY" and price > Decimal(str(order["price"]))) or (
                    side == "SELL" and price < Decimal(str(order["price"]))
                ):
                    price = Decimal(str(order["price"]))

            leverage = self.set_leverage()

            if quantity * price / leverage < self.unit:
                # removes order if it's less than 1 dollar in value
                orders.remove(order)
                self.db.update(dict(orders=orders))
                logging.info(f"{price} - Order not processed: value must be greater than 1 usd")
                return False

            if (side == "BUY" and self.position.side in [0, 1]) or (
                side == "SELL" and self.position.side in [-1, 0]
            ):  # open or increase position
                fee = quantity * price * self.fee_rate
                cost = quantity * price / leverage + fee
                if self.balance >= cost:
                    self.balance -= cost
                    self.position.side = 1 if side == "BUY" else -1
                    self.position.increase(quantity, price)
                    orders.remove(order)
                    self.db.update(dict(orders=orders))
                    logging.info(f"{price} - Order processed: {side} : {quantity} @ {price}")
                    return True
                else:  # not enough balance
                    orders.remove(order)
                    self.db.update(dict(orders=orders))
                    logging.info(f"{price} - Order not processed: not enough balance")
                    return False

            else:  # close or decrease position
                if self.position.quantity >= quantity:
                    # close or decrease position
                    initial, pnl = self.position.decrease(quantity, price)
                    fee = (initial + pnl) * self.fee_rate
                    self.balance += initial / leverage + pnl - fee
                    orders.remove(order)
                    self.db.update(dict(orders=orders))
                    logging.info(f"{price} - Order processed: {side} : {quantity} @ {price}")
                    return True
                else:
                    # close and open reverse position
                    remaining = quantity - self.position.quantity
                    fee = remaining * price * self.fee_rate
                    cost = remaining * price / leverage + fee
                    total_balance = self.balance + self.position.value(price, self.fee_rate)
                    if total_balance >= cost:
                        # close position and get returns
                        initial, pnl = self.position.decrease(self.position.quantity, price)
                        fee = (initial + pnl) * self.fee_rate
                        self.balance += initial / leverage + pnl - fee
                        # starts new position with remaining quantity
                        self.balance -= cost
                        self.position.side = 1 if side == "BUY" else -1
                        self.position.increase(remaining, price)
                        orders.remove(order)
                        self.db.update(dict(orders=orders))
                        logging.info(f"{price} - Order processed: {side} : {quantity} @ {price}")
                        return True
                    else:  # not enough balance
                        orders.remove(order)
                        self.db.update(dict(orders=orders))
                        logging.info(f"{price} - Order not processed: not enough balance")
                        return False

    def liquidation_check(self, price: Decimal):
        """
        checks position liquidation in a given price
        closes position if it's liquidated
        """
        liquidation_price = self.position.liquidation_price(self.fee_rate)
        if (self.position.side == 1 and price <= liquidation_price) or (
            self.position.side == -1 and price >= liquidation_price
        ):
            self.position.decrease(self.position.quantity, price)
            logging.info(f"{price} - Position liquidated")
            return True
        return False

    def start(self):
        """
        starts server with given arguments
        1.receive last price from websocket
        2.submit order to orders list
        3.check for position liquidation in last price
        4.process orders with last price
        5.update database
        """
        logging.info(f"Server started for {self.symbol.upper()}")

        while True:
            price = self.last_price()
            self.submit_order()
            self.liquidation_check(price)
            self.process_orders(price)
            self.db.update(
                dict(
                    time=datetime.datetime.now().strftime("%H:%M:%S"),
                    price=float(price),
                    balance=float(self.balance),
                    value=float(self.balance + self.position.value(price, self.fee_rate)),
                    position=self.position.to_dict(price, self.fee_rate),
                )
            )
            if self.position.side != 0:
                pos = str(self.position)
                lev = self.position.leverage
                liq = round(self.position.liquidation_price(self.fee_rate), 2)
                pnl = round(self.position.pnl(price), 2)
                mar = self.position.margin(price)
                logging.info(f"{price} - Position: {pos} lev:{lev}X liq:{liq}$ pnl:{pnl}$ margin:{mar}")
            else:
                logging.info(f"{price}")

            time.sleep(1)


if __name__ == "__main__":

    parser = argparse.ArgumentParser("binance futures simulator")
    parser.add_argument("-s", "--symbol")
    parser.add_argument("-b", "--balance")
    parser.add_argument("-f", "--fee")
    args = parser.parse_args()

    server = Server(symbol=args.symbol, balance=int(args.balance), fee_rate=float(args.fee))

    server.start()

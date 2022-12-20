from tinydb import TinyDB


class Client:
    def __init__(self):
        self.db = TinyDB("database.json")

    def get_price(self):
        """
        gets last price
        """
        return float(self.db.all()[0]["price"])

    def get_account(self):
        """
        gets account balance and total value(balance+position)
        """
        balance = self.db.all()[0]["balance"]
        value = self.db.all()[0]["value"]
        return {"balance": balance, "value": value}

    def set_leverage(self, leverage: int):
        """
        sets leverage
        leverage will be set if there is no open positon
        """
        self.db.update(dict(leverage=leverage))

    def submit_order(self, side: str, quantity: float, price: float = None):
        """
        submits orders
        don't submit more than one order in a second
        """
        assert side.upper() in ["BUY", "SELL"]
        assert quantity > 0.0
        assert price > 0.0 if price else True
        order = dict(side=side.upper(), quantity=quantity, price=price)
        self.db.update(dict(order=order))
        return True

    def get_orders(self):
        """
        gets all open orders
        """
        orders = self.db.all()[0]["orders"]
        return orders

    def cancel_order(self, id: int):
        """
        cancels order given id
        """
        orders = self.db.all()[0]["orders"]
        for order in orders:
            if order["id"] == id:
                orders.remove(order)
                self.db.update(dict(orders=orders))
                return True
        return False

    def close_position(self, price: float = None):
        """
        closes position with given price (limit) or no price (market)
        """
        assert price > 0.0 if price else True
        position = self.db.all()[0]["position"]
        if position["side"] != "None":
            side = "SELL" if position["side"] == "Long" else "BUY"
            quantity = float(position["quantity"])
            order = dict(side=side, quantity=quantity, price=price)
            self.db.update(dict(order=order))

    def get_position(self):
        """
        gets position info
        """
        position = self.db.all()[0]["position"]
        return position

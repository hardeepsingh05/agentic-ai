import datetime
from typing import Dict, List, Optional, Literal

# In-memory store for accounts
_accounts: Dict[str, 'Account'] = {}

class Transaction:
    def __init__(self, tx_type: Literal["deposit", "withdraw", "buy", "sell"], 
                 symbol: str, qty: int, price_per_share: float, 
                 timestamp: datetime.datetime, amount: float):
        self.tx_type = tx_type
        self.symbol = symbol
        self.qty = qty
        self.price_per_share = price_per_share
        self.timestamp = timestamp
        self.amount = amount

    def __repr__(self):
        return f"Transaction({self.tx_type}, {self.symbol}, {self.qty}, {self.price_per_share}, {self.timestamp}, {self.amount})"

class Account:
    def __init__(self, user_id: str, initial_deposit: float):
        self.user_id = user_id
        self.balance = initial_deposit  # cash balance
        self.holdings: Dict[str, int] = {}  # symbol -> quantity
        self.transactions: List[Transaction] = []
        self.initial_deposit = initial_deposit
        # Record the initial deposit as a transaction
        self._record_transaction("deposit", "", 0, 0.0, initial_deposit)

    def _record_transaction(self, tx_type: Literal["deposit", "withdraw", "buy", "sell"], 
                            symbol: str, qty: int, price_per_share: float, 
                            cash_change: float) -> None:
        """Record a transaction in the account's transaction list."""
        timestamp = datetime.datetime.now()
        # For buy/sell, amount is the market value (qty * price_per_share) with sign?
        # But the design says: amount is cash impact (deposit/withdraw) or market value (trade)
        # For deposit/withdraw: amount = cash_change (positive for deposit, negative for withdraw)
        # For buy: amount = - (qty * price_per_share)  (cash outflow)
        # For sell: amount = + (qty * price_per_share)  (cash inflow)
        if tx_type in ["buy", "sell"]:
            amount = qty * price_per_share
            if tx_type == "buy":
                amount = -amount  # cash outflow
            else:
                amount = amount   # cash inflow
        else:
            amount = cash_change  # deposit: positive, withdraw: negative
        tx = Transaction(tx_type, symbol, qty, price_per_share, timestamp, amount)
        self.transactions.append(tx)

    def deposit(self, amount: float) -> bool:
        if amount <= 0:
            return False
        self.balance += amount
        self._record_transaction("deposit", "", 0, 0.0, amount)
        return True

    def withdraw(self, amount: float) -> bool:
        if amount <= 0:
            return False
        if self.balance - amount < 0:
            return False
        self.balance -= amount
        self._record_transaction("withdraw", "", 0, 0.0, -amount)
        return True

    def buy_shares(self, symbol: str, qty: int, current_price: float) -> bool:
        if qty <= 0:
            return False
        cost = qty * current_price
        if cost > self.balance:
            return False
        # Update balance and holdings
        self.balance -= cost
        self.holdings[symbol] = self.holdings.get(symbol, 0) + qty
        self._record_transaction("buy", symbol, qty, current_price, -cost)
        return True

    def sell_shares(self, symbol: str, qty: int, current_price: float) -> bool:
        if qty <= 0:
            return False
        if self.holdings.get(symbol, 0) < qty:
            return False
        # Update balance and holdings
        proceeds = qty * current_price
        self.balance += proceeds
        self.holdings[symbol] -= qty
        if self.holdings[symbol] == 0:
            del self.holdings[symbol]
        self._record_transaction("sell", symbol, qty, current_price, proceeds)
        return True

    def get_portfolio_value(self, get_share_price_func) -> float:
        """Calculate total market value = cash balance + sum(holdings[symbol] * current_price)."""
        total = self.balance
        for symbol, qty in self.holdings.items():
            price = get_share_price_func(symbol)
            total += qty * price
        return total

    def get_profit_loss(self, get_share_price_func) -> float:
        """Return portfolio_value - initial_deposit."""
        return self.get_portfolio_value(get_share_price_func) - self.initial_deposit

    def get_holdings(self) -> Dict[str, int]:
        """Return a copy of the user's current share holdings."""
        return self.holdings.copy()

    def get_transactions(self) -> List[Transaction]:
        """Return a copy of the transaction list (ordered by timestamp)."""
        return self.transactions.copy()


def create_account(user_id: str, initial_deposit: float) -> bool:
    """Register a new user with an opening cash deposit; fails if user_id already exists or deposit <= 0."""
    if initial_deposit <= 0 or user_id in _accounts:
        return False
    account = Account(user_id, initial_deposit)
    _accounts[user_id] = account
    return True

def get_account(user_id: str) -> Optional[Account]:
    """Helper to retrieve account by user_id."""
    return _accounts.get(user_id)

def deposit(user_id: str, amount: float) -> bool:
    """Add cash to balance; amount must be > 0."""
    account = get_account(user_id)
    if not account:
        return False
    return account.deposit(amount)

def withdraw(user_id: str, amount: float) -> bool:
    """Subtract cash from balance; must leave balance >= 0."""
    account = get_account(user_id)
    if not account:
        return False
    return account.withdraw(amount)

def buy_shares(user_id: str, symbol: str, qty: int, current_price: float) -> bool:
    """Record a purchase; validates that qty * current_price <= balance; updates holdings and balance."""
    account = get_account(user_id)
    if not account:
        return False
    return account.buy_shares(symbol, qty, current_price)

def sell_shares(user_id: str, symbol: str, qty: int, current_price: float) -> bool:
    """Record a sale; validates that qty <= holdings[symbol]; updates holdings, balance, and records transaction."""
    account = get_account(user_id)
    if not account:
        return False
    return account.sell_shares(symbol, qty, current_price)

def get_portfolio_value(user_id: str, get_share_price_func) -> float:
    """Returns total market value = cash balance + sum(holdings[symbol] * current_price)."""
    account = get_account(user_id)
    if not account:
        return 0.0
    return account.get_portfolio_value(get_share_price_func)

def get_profit_loss(user_id: str, get_share_price_func) -> float:
    """Returns portfolio_value - initial_deposit."""
    account = get_account(user_id)
    if not account:
        return 0.0
    return account.get_profit_loss(get_share_price_func)

def get_holdings(user_id: str) -> Dict[str, int]:
    """Returns a copy of the user's current share holdings."""
    account = get_account(user_id)
    if not account:
        return {}
    return account.get_holdings()

def get_transactions(user_id: str) -> List[Transaction]:
    """Returns the full transaction list (ordered by timestamp)."""
    account = get_account(user_id)
    if not account:
        return []
    return account.get_transactions()

def get_share_price(symbol: str) -> float:
    """Wrapper that calls the provided external price service; 
    returns fixed prices for AAPL, TSLA, GOOGL for testing."""
    # Fixed test prices
    prices = {
        "AAPL": 150.0,
        "TSLA": 800.0,
        "GOOGL": 2500.0
    }
    return prices.get(symbol, 0.0)  # Return 0.0 for unknown symbols (could also raise)
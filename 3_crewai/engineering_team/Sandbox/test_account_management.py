import unittest
from account_management import (create_account, deposit, withdraw, buy_shares, sell_shares,
                                get_portfolio_value, get_profit_loss, get_holdings,
                                get_transactions, get_share_price, get_account)


class TestAccountManagement(unittest.TestCase):

    def setUp(self):
        # Clear the accounts dictionary before each test
        global _accounts
        # Re-import to reset state
        import account_management
        account_management._accounts.clear()

    def test_create_account_success(self):
        result = create_account("user1", 1000.0)
        self.assertTrue(result)
        account = get_account("user1")
        self.assertIsNotNone(account)
        self.assertEqual(account.balance, 1000.0)

    def test_create_account_duplicate(self):
        create_account("user1", 1000.0)
        result = create_account("user1", 500.0)
        self.assertFalse(result)

    def test_create_account_negative_deposit(self):
        result = create_account("user1", -500.0)
        self.assertFalse(result)
        result2 = create_account("user2", 0)
        self.assertFalse(result2)

    def test_deposit_positive(self):
        create_account("user1", 1000.0)
        result = deposit("user1", 500.0)
        self.assertTrue(result)
        account = get_account("user1")
        self.assertEqual(account.balance, 1500.0)

    def test_deposit_zero_or_negative(self):
        create_account("user1", 1000.0)
        result = deposit("user1", 0)
        self.assertFalse(result)
        result2 = deposit("user1", -100.0)
        self.assertFalse(result2)
        account = get_account("user1")
        self.assertEqual(account.balance, 1000.0)

    def test_withdraw_success(self):
        create_account("user1", 1000.0)
        result = withdraw("user1", 300.0)
        self.assertTrue(result)
        account = get_account("user1")
        self.assertEqual(account.balance, 700.0)
        txns = get_transactions("user1")
        # Initial deposit + 1 withdraw = 2 transactions
        self.assertEqual(len(txns), 2)

    def test_withdraw_negative_balance(self):
        create_account("user1", 1000.0)
        result = withdraw("user1", 1500.0)
        self.assertFalse(result)
        account = get_account("user1")
        self.assertEqual(account.balance, 1000.0)

    def test_buy_shares_affordable(self):
        create_account("user1", 10000.0)
        price = get_share_price("AAPL")
        result = buy_shares("user1", "AAPL", 5, price)
        self.assertTrue(result)
        account = get_account("user1")
        self.assertEqual(account.holdings["AAPL"], 5)
        expected_balance = 10000 - 5 * price
        self.assertAlmostEqual(account.balance, expected_balance, places=2)

    def test_buy_shares_insufficient_funds(self):
        create_account("user1", 100.0)
        price = get_share_price("AAPL")
        result = buy_shares("user1", "AAPL", 10, price)  # cost > 100
        self.assertFalse(result)
        account = get_account("user1")
        self.assertNotIn("AAPL", account.holdings)

    def test_sell_shares_owned(self):
        create_account("user1", 10000.0)
        price = get_share_price("AAPL")
        buy_shares("user1", "AAPL", 10, price)
        result = sell_shares("user1", "AAPL", 5, price)
        self.assertTrue(result)
        account = get_account("user1")
        self.assertEqual(account.holdings["AAPL"], 5)
        expected_balance = (10000 - 10 * price) + 5 * price
        self.assertAlmostEqual(account.balance, expected_balance, places=2)

    def test_sell_shares_not_owned(self):
        create_account("user1", 1000.0)
        result = sell_shares("user1", "TSLA", 5, 800.0)
        self.assertFalse(result)
        account = get_account("user1")
        self.assertNotIn("TSLA", account.holdings)

    def test_sell_shares_excess_quantity(self):
        create_account("user1", 10000.0)
        price = get_share_price("AAPL")
        buy_shares("user1", "AAPL", 5, price)
        result = sell_shares("user1", "AAPL", 10, price)  # only own 5
        self.assertFalse(result)
        account = get_account("user1")
        self.assertEqual(account.holdings["AAPL"], 5)

    def test_portfolio_value_calculation(self):
        create_account("user1", 10000.0)
        price_aapl = get_share_price("AAPL")
        price_go = get_share_price("GOOGL")
        buy_shares("user1", "AAPL", 10, price_aapl)
        buy_shares("user1", "GOOGL", 2, price_go)
        portfolio_val = get_portfolio_value("user1", get_share_price)
        expected = 10000 - 10 * price_aapl - 2 * price_go + 10 * price_aapl + 2 * price_go
        self.assertAlmostEqual(portfolio_val, expected, places=2)

    def test_profit_loss_basic(self):
        create_account("user1", 10000.0)
        price = get_share_price("AAPL")
        buy_shares("user1", "AAPL", 10, price)
        # If price stays the same, profit = 0
        pl = get_profit_loss("user1", get_share_price)
        self.assertAlmostEqual(pl, 0.0, places=2)

    def test_get_transactions_ordering(self):
        create_account("user1", 1000.0)
        deposit("user1", 500.0)
        withdraw("user1", 300.0)
        txns = get_transactions("user1")
        self.assertEqual(len(txns), 3)
        # Check timestamps are non-decreasing
        timestamps = [tx.timestamp for tx in txns]
        self.assertEqual(timestamps, sorted(timestamps))

    def test_integration_multiple_operations(self):
        create_account("user1", 10000.0)
        deposit("user1", 5000.0)
        price_aapl = get_share_price("AAPL")
        price_tsla = get_share_price("TSLA")
        # Buy 10 shares of AAPL
        buy_shares("user1", "AAPL", 10, price_aapl)
        # Sell 5 shares of AAPL
        sell_shares("user1", "AAPL", 5, price_aapl)
        # Withdraw 2000
        withdraw("user1", 2000.0)
        account = get_account("user1")
        # Balance should be 10000 + 5000 - 10*price + 5*price - 2000 = 13000 - 5*price
        expected_balance = 15000 - 10 * price_aapl + 5 * price_aapl - 2000
        self.assertAlmostEqual(account.balance, expected_balance, places=2)
        self.assertEqual(account.holdings["AAPL"], 5)
        txns = get_transactions("user1")
        # initial deposit + deposit + buy + sell + withdraw = 5 txns
        self.assertEqual(len(txns), 5)


if __name__ == "__main__":
    unittest.main()
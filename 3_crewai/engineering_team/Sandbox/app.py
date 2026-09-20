import gradio as gr
from account_management import (create_account, deposit, withdraw, buy_shares, sell_shares,
                                get_portfolio_value, get_profit_loss, get_share_price,
                                get_account)

# ---------- Callback Functions ----------
def handle_create_account(user_id: str, initial_deposit: float, state: dict):
    if "accounts" not in state:
        state["accounts"] = {}
    if user_id in state["accounts"]:
        return state, "User ID already exists."
    if initial_deposit <= 0:
        return state, "Initial deposit must be positive."
    if not create_account(user_id, initial_deposit):
        return state, "Failed to create account."
    account = get_account(user_id)
    if account:
        state["accounts"][user_id] = account
    return state, "Account created successfully."

def handle_deposit(user_id: str, amount: float, state: dict):
    if "accounts" not in state or user_id not in state["accounts"]:
        return state, "Account not found."
    if amount <= 0:
        return state, "Deposit amount must be positive."
    if not deposit(user_id, amount):
        return state, "Deposit failed."
    return state, "Deposit successful."

def handle_withdraw(user_id: str, amount: float, state: dict):
    if "accounts" not in state or user_id not in state["accounts"]:
        return state, "Account not found."
    if amount <= 0:
        return state, "Withdraw amount must be positive."
    if not withdraw(user_id, amount):
        return state, "Withdrawal failed (would cause negative balance)."
    return state, "Withdrawal successful."

def handle_buy(user_id: str, symbol: str, qty: int, state: dict):
    if "accounts" not in state or user_id not in state["accounts"]:
        return state, 0.0, "Account not found."
    price = get_share_price(symbol)
    if price == 0:
        return state, 0.0, "Unknown symbol."
    if qty <= 0:
        return state, 0.0, "Quantity must be positive."
    if not buy_shares(user_id, symbol, qty, price):
        return state, 0.0, "Buy failed (insufficient funds or invalid quantity)."
    portfolio_val = get_portfolio_value(user_id, get_share_price)
    return state, portfolio_val, f"Bought {qty} shares of {symbol} at ${price:.2f}."

def handle_sell(user_id: str, symbol: str, qty: int, state: dict):
    if "accounts" not in state or user_id not in state["accounts"]:
        return state, 0.0, "Account not found."
    price = get_share_price(symbol)
    if price == 0:
        return state, 0.0, "Unknown symbol."
    if qty <= 0:
        return state, 0.0, "Quantity must be positive."
    if not sell_shares(user_id, symbol, qty, price):
        return state, 0.0, "Sell failed (insufficient holdings or invalid quantity)."
    pl = get_profit_loss(user_id, get_share_price)
    return state, pl, f"Sold {qty} shares of {symbol} at ${price:.2f}."

def show_portfolio(state: dict):
    accounts = state.get("accounts", {})
    if not accounts:
        return {"text": "No accounts created yet."}
    # For demonstration, show the first user's data
    first_user = next(iter(accounts))
    account = accounts[first_user]
    holdings = account.get_holdings()
    portfolio_val = account.get_portfolio_value(get_share_price)
    return {
        "holdings": holdings,
        "portfolio_value": portfolio_val
    }

def show_transactions(state: dict):
    accounts = state.get("accounts", {})
    if not accounts:
        return "No transactions recorded."
    first_user = next(iter(accounts))
    account = accounts[first_user]
    txns = account.get_transactions()
    if not txns:
        return "No transactions recorded."
    lines = ["Timestamp | Type | Symbol | Qty | Price | Amount"]
    for tx in txns:
        lines.append(f"{tx.timestamp} | {tx.tx_type} | {tx.symbol} | {tx.qty} | {tx.price_per_share} | {tx.amount}")
    return "\n".join(lines)

# ---------- Gradio UI ----------
def build_ui() -> gr.Blocks:
    with gr.Blocks() as demo:
        gr.Markdown("# Trading Simulation Account Management")

        # Hidden state container
        state = gr.State(value={})

        # ---- Account Creation ----
        with gr.Row():
            user_id_input = gr.Textbox(label="User ID")
            initial_deposit_input = gr.Number(label="Initial Deposit")
        create_account_btn = gr.Button("Create Account")
        create_account_msg = gr.Textbox(label="Create Account Message", interactive=False)

        # ---- Deposit ----
        deposit_amount_input = gr.Number(label="Deposit Amount")
        deposit_btn = gr.Button("Deposit")
        deposit_msg = gr.Textbox(label="Deposit Message", interactive=False)

        # ---- Withdraw ----
        withdraw_amount_input = gr.Number(label="Withdraw Amount")
        withdraw_btn = gr.Button("Withdraw")
        withdraw_msg = gr.Textbox(label="Withdraw Message", interactive=False)

        # ---- Buy Shares ----
        symbol_input = gr.Textbox(label="Symbol")
        qty_input = gr.Number(label="Quantity")
        buy_btn = gr.Button("Buy")
        buy_msg = gr.Textbox(label="Buy Message", interactive=False)
        portfolio_value_output = gr.Textbox(label="Portfolio Value", interactive=False)

        # ---- Sell Shares ----
        sell_symbol_input = gr.Textbox(label="Symbol")
        sell_qty_input = gr.Number(label="Quantity")
        sell_btn = gr.Button("Sell")
        sell_msg = gr.Textbox(label="Sell Message", interactive=False)
        profit_loss_output = gr.Textbox(label="Profit/Loss", interactive=False)

        # ---- Portfolio & Transactions Views ----
        show_portfolio_btn = gr.Button("Show Portfolio")
        portfolio_display = gr.Code(label="Portfolio Details")

        show_transactions_btn = gr.Button("Show Transactions")
        transactions_display = gr.Code(label="Transactions")

        # Wire callbacks
        create_account_btn.click(
            fn=handle_create_account,
            inputs=[user_id_input, initial_deposit_input, state],
            outputs=[state, create_account_msg]
        )
        deposit_btn.click(
            fn=handle_deposit,
            inputs=[user_id_input, deposit_amount_input, state],
            outputs=[state, deposit_msg]
        )
        withdraw_btn.click(
            fn=handle_withdraw,
            inputs=[user_id_input, withdraw_amount_input, state],
            outputs=[state, withdraw_msg]
        )
        buy_btn.click(
            fn=handle_buy,
            inputs=[user_id_input, symbol_input, qty_input, state],
            outputs=[state, buy_msg, portfolio_value_output]
        )
        sell_btn.click(
            fn=handle_sell,
            inputs=[user_id_input, sell_symbol_input, sell_qty_input, state],
            outputs=[state, sell_msg, profit_loss_output]
        )
        show_portfolio_btn.click(
            fn=show_portfolio,
            inputs=[state],
            outputs=[portfolio_display]
        )
        show_transactions_btn.click(
            fn=show_transactions,
            inputs=[state],
            outputs=[transactions_display]
        )

    return demo

def start_app() -> None:
    demo = build_ui()
    demo.launch()

# Allow direct execution
if __name__ == "__main__":
    start_app()
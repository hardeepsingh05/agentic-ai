# Detailed Design for the Trading‑Simulation Account Management System  

**Scope** – Provide a complete, modular design that satisfies every requirement, allocates work to the three engineers, and includes Gradio 6 guidance for the frontend implementation.  
All files live in a single directory inside a `uv` project with Gradio 6 installed. No sub‑folders or packages are used.

---  

## 1. High‑Level Architecture  

| Layer | Responsibility | Primary Engineer |
|-------|----------------|------------------|
| **Backend** | Business logic, data persistence (in‑memory), validation, integration with `get_share_price` | **backend_engineer** |
| **Frontend** | Interactive UI built with Gradio 6, calls backend functions, maintains state across calls | **frontend_engineer** |
| **Tests** | Automated unit tests that verify every backend operation and edge‑case | **test_engineer** |

All communication between Frontend and Backend happens via direct Python function calls; the Gradio app simply forwards user actions to these backend functions and displays the returned values.

---  

## 2. Module Overview  

| File (single‑directory) | Purpose |
|--------------------------|---------|
| `account_management.py` | Backend implementation – classes, data models, and public API functions |
| `app.py` | Gradio 6 application – UI components, event wiring, state handling |
| `test_account_management.py` | Unit‑test suite for `account_management.py` |

---  

## 3. Backend Design (`account_management.py`)  

### 3.1 Core Data Models  

```text
Account
│
├─ user_id        : str               # Unique identifier for the user
├─ balance        : float             # Cash balance (cannot go negative)
├─ holdings       : dict[str, int]    # Symbol → quantity of shares owned
├─ transactions   : list[Transaction] # Chronological record of all actions
└─ initial_deposit: float             # Original cash deposit (for P/L calc)
```

```text
Transaction
│
├─ tx_type        : Literal["deposit","withdraw","buy","sell"]   # Kind of operation
├─ symbol        : str                    # Stock ticker (e.g., "AAPL")
├─ qty           : int                    # Positive for buy/sell, negative for withdraw?
├─ price_per_share : float               # Executed price (from get_share_price)
├─ timestamp     : datetime               # When the transaction occurred
└─ amount        : float                  # Cash impact (deposit/withdraw) or market value (trade)
```

### 3.2 Public API Functions (signatures only)  

| Function | Signature | Description |
|----------|-----------|-------------|
| `create_account` | `def create_account(user_id: str, initial_deposit: float) -> bool` | Register a new user with an opening cash deposit; fails if `user_id` already exists or deposit ≤ 0. |
| `deposit` | `def deposit(user_id: str, amount: float) -> bool` | Add cash to `balance`; amount must be > 0. |
| `withdraw` | `def withdraw(user_id: str, amount: float) -> bool` | Subtract cash from `balance`; must leave `balance ≥ 0`. |
| `buy_shares` | `def buy_shares(user_id: str, symbol: str, qty: int, current_price: float) -> bool` | Record a purchase; validates that `qty * current_price ≤ balance`; updates `holdings` and `balance`. |
| `sell_shares` | `def sell_shares(user_id: str, symbol: str, qty: int, current_price: float) -> bool` | Record a sale; validates that `qty ≤ holdings[symbol]`; updates `holdings`, `balance`, and records transaction. |
| `get_portfolio_value` | `def get_portfolio_value(user_id: str) -> float` | Returns total market value = cash balance + sum(holdings[symbol] * current_price). |
| `get_profit_loss` | `def get_profit_loss(user_id: str) -> float` | Returns `portfolio_value - initial_deposit`. |
| `get_holdings` | `def get_holdings(user_id: str) -> dict[str, int]` | Returns a copy of the user's current share holdings. |
| `get_transactions` | `def get_transactions(user_id: str) -> list[Transaction]` | Returns the full transaction list (ordered by timestamp). |
| `get_share_price` | `def get_share_price(symbol: str) -> float` | Wrapper that calls the provided external price service; already provided with fixed test values for AAPL, TSLA, GOOGL. |

> **Validation Rules (enforced inside each function)**  
> - No withdrawal that would push `balance` below 0.  
> - No purchase that would require spending more cash than `balance` permits.  
> - No sale of a symbol the user does not own, or of a quantity exceeding current holdings.  

### 3.3 Helper Functions (internal)  

| Function | Signature | Purpose |
|----------|-----------|---------|
| `_record_transaction` | `def _record_transaction(user_id: str, tx_type: str, symbol: str, qty: int, price: float, cash_change: float) -> None` | Append a new `Transaction` to `account.transactions` with appropriate `amount` and timestamp. |
| `_validate_symbol` | `def _validate_symbol(symbol: str) -> bool` | Checks that `symbol` is non‑empty and supported (leverages `get_share_price`). |
| `_apply_buy` | `def _apply_buy(user_id: str, qty: int, price: float) -> None` | Updates `holdings`, `balance`, and records transaction. |
| `_apply_sell` | `def _apply_sell(user_id: str, qty: int, price: float) -> None` | Updates `holdings`, `balance`, and records transaction. |

---  

## 4. Frontend Design (`app.py`) – Gradio 6  

### 4.1 Gradio 6 API Overview (key changes)  

* **Layout** – Use `gr.Blocks()` as the top‑level container; components are created inside a `with` block.  
* **State** – Persistent application state is stored with `gr.State`.  
* **Event binding** – Component methods (`.click`, `.submit`, `.change`) accept **`inputs`** and **`outputs`** lists; the callback function receives the **current state** as positional arguments.  
* **Examples** – Pass a list of example payloads directly to the `examples=` argument (each example is a list matching the `inputs` order).  
* **Return values** – Functions must return a tuple that matches the **`outputs`** specification; for UI updates you typically return a value for each output component.  

### 4.2 Public Gradio Functions (signatures only)  

```text
def build_ui() -> gr.Blocks
```

*Creates and returns the complete Gradio interface. No parameters.*

```text
def start_app() -> None
```

*Launches the Gradio demo (`demo.launch()`). Accepts no arguments; all configuration is done inside `build_ui`.*

```text
def handle_create_account(user_id: str, initial_deposit: float, state: dict) -> tuple[dict, str]
```

*Callback for “Create Account” button. Returns updated state dict and a status message.*

```text
def handle_deposit(user_id: str, amount: float, state: dict) -> tuple[dict, str]
```

*Callback for “Deposit” button.*

```text
def handle_withdraw(user_id: str, amount: float, state: dict) -> tuple[dict, str]
```

*Callback for “Withdraw” button.*

```text
def handle_buy(user_id: str, symbol: str, qty: int, state: dict) -> tuple[dict, float, str]
```

*Callback for “Buy Shares” button. Returns updated state, current portfolio value, and a message.*

```text
def handle_sell(user_id: str, symbol: str, qty: int, state: dict) -> tuple[dict, float, str]
```

*Callback for “Sell Shares” button. Returns updated state, current profit/loss, and a message.*

```text
def show_portfolio(state: dict) -> dict
```

*Callback for “Show Portfolio” button. Returns a dictionary that will be rendered as a formatted text block (e.g., holdings + values).*

```text
def show_transactions(state: dict) -> str
```

*Callback for “Show Transactions” button. Returns a formatted multiline string listing all txns.*

### 4.3 Component Wiring (high‑level description)  

| UI Element | Component Type (Gradio 6) | Connected Callback | Inputs (order) | Outputs (order) |
|------------|---------------------------|--------------------|----------------|-----------------|
| Account ID field | `gr.Textbox(label="User ID")` | `handle_create_account` | `[user_id, initial_deposit, state]` | `[updated_state, message]` |
| Deposit amount field | `gr.Number(label="Amount")` | `handle_deposit` | `[user_id, amount, state]` | `[updated_state, message]` |
| Withdraw amount field | `gr.Number(label="Amount")` | `handle_withdraw` | `[user_id, amount, state]` | `[updated_state, message]` |
| Symbol entry | `gr.Textbox(label="Symbol")` | `handle_buy` / `handle_sell` | `[user_id, symbol, qty, state]` | `[updated_state, portfolio_value_or_pl, message]` |
| Quantity entry | `gr.Number(label="Quantity")` | `handle_buy` / `handle_sell` | same as above | same as above |
| Buy button | `gr.Button("Buy")` | `handle_buy` | – | – |
| Sell button | `gr.Button("Sell")` | `handle_sell` | – | – |
| Portfolio view | `gr.Button("Show Portfolio")` | `show_portfolio` | `[state]` | `[formatted_portfolio_text]` |
| Transactions view | `gr.Button("Show Transactions")` | `show_transactions` | `[state]` | `[formatted_tx_list]` |
| Persistent store | `gr.State(value={})` | Shared across all callbacks | – | – |

*All callbacks receive the **same** `state` object (a mutable dictionary) that holds the current `Account` data for the active user. The dictionary is updated in‑place and returned to keep Gradio’s internal state consistent.*

---  

## 5. Test Engineer Deliverables (`test_account_management.py`)  

Only function **signatures** and brief purpose statements are required; no implementation code.

| Test Function | Signature | Intent |
|---------------|-----------|--------|
| `test_create_account_success` | `def test_create_account_success():` | Verifies that a new account is created with a positive balance and that duplicate IDs are rejected. |
| `test_create_account_negative_deposit` | `def test_create_account_negative_deposit():` | Ensures creation fails when `initial_deposit ≤ 0`. |
| `test_deposit_positive` | `def test_deposit_positive():` | Confirms that a valid deposit increases `balance`. |
| `test_deposit_zero_or_negative` | `def test_deposit_zero_or_negative():` | Deposit must be > 0; test that it fails otherwise. |
| `test_withdraw_success` | `def test_withdraw_success():` | Valid withdrawal leaves a non‑negative balance and updates transaction list. |
| `test_withdraw_negative_balance` | `def test_withdraw_negative_balance():` | Attempt to withdraw beyond balance must fail. |
| `test_buy_shares_affordable` | `def test_buy_shares_affordable():` | Purchase succeeds when enough cash is available; holdings and balance update correctly. |
| `test_buy_shares_insufficient_funds` | `def test_buy_shares_insufficient_funds():` | Purchase fails when required cash exceeds balance. |
| `test_sell_shares_owned` | `def test_sell_shares_owned():` | Sale succeeds when the user holds enough shares; updates holdings and balance. |
| `test_sell_shares_not_owned` | `def test_sell_shares_not_owned():` | Sale fails when the user has zero of the symbol. |
| `test_sell_shares_excess_quantity` | `def test_sell_shares_excess_quantity():` | Sale fails when requested quantity > owned quantity. |
| `test_portfolio_value_calculation` | `def test_portfolio_value_calculation():` | Confirms that `get_portfolio_value` equals cash + market value of holdings. |
| `test_profit_loss_basic` | `def test_profit_loss_basic():` | Verifies that profit/loss equals portfolio value minus initial deposit. |
| `test_get_transactions_ordering` | `def test_get_transactions_ordering():` | Ensures returned transaction list is chronological. |
| `test_integration_multiple_operations` | `def test_integration_multiple_operations():` | End‑to‑end scenario: create account → deposit → buy → sell → withdraw; final state matches expectations. |

*Each test imports `account_management` and uses its public functions directly; no Gradio code is included in the test suite.*

---  

## 6. Engineer Assignments  

| Engineer | Primary Files / Responsibilities |
|----------|-----------------------------------|
| **backend_engineer** | - Implement `account_management.py` with all classes (`Account`, `Transaction`), helper methods, and the public API functions listed in Section 3. <br> - Provide the in‑memory data store (dictionary keyed by `user_id`). <br> - Ensure all validation rules are enforced. |
| **frontend_engineer** | - Implement `app.py` using Gradio 6: create `build_ui()` and `start_app()` as described. <br> - Wire all UI components to the callbacks listed in Section 4.2, passing the shared `state` dictionary. <br> - Handle state persistence across callbacks with `gr.State`. <br> - Include example inputs for the interface. |
| **test_engineer** | - Implement `test_account_management.py` containing all function signatures from Section 5. <br> - Each test must be import‑able and call the backend API to verify expected behaviour. <br> - No external test framework beyond standard `unittest`/`pytest` (available in the sandbox). |

---  

## 7. Success Criteria Checklist  

1. **Account creation** works with a positive initial deposit and rejects invalid inputs.  
2. **Deposit / Withdraw** update cash balance while preserving non‑negative constraint.  
3. **Buy / Sell** operations respect affordability and ownership limits, update holdings, and record transactions.  
4. **Portfolio value**, **profit/loss**, **holdings**, and **transaction list** can be queried at any time and reflect the latest state.  
5. **Gradio UI** launches without errors, correctly calls backend functions, and displays up‑to‑date information.  
6. **Unit‑test suite** runs completely and passes all scenarios, providing confidence that the backend behaves as specified.  

---  

### End of Design  

*All specifications above are expressed as signatures and descriptive text only; no actual implementation code is included.*
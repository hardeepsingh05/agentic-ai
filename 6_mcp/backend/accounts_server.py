try:
    from mcp.server.mcpserver import MCPServer as FastMCP  # mcp 2.x
except ImportError:
    from mcp.server.fastmcp import FastMCP  # mcp 1.x
from .accounts import Account

mcp = FastMCP("accounts_server")

@mcp.tool()
async def get_balance(name: str) -> float:
    """
    Get the cash balance of the given account name.

    Args:
        name: The name of the account holder

    Returns:
        Balance of the account holder as floating number.
    """
    return Account.get(name).balance

@mcp.tool()
async def get_holdings(name: str) -> dict[str, int]:
    """
    Get the holdings of the given account name.

    Args:
        name: The name of the account holder

    Returns:
        A dictionary containing information on holdings of the holder.
    """
    return Account.get(name).holdings

@mcp.tool()
async def buy_shares(name: str, symbol: str, quantity: int, rationale: str) -> str:
    """
    Buy shares of a stock.

    Args:
        name: The name of the account holder
        symbol: The symbol of the stock
        quantity: The quanity of shares to buy
        rationale: The rationale for the purchase and fit with the account's strategy
    
    Returns:
        A string containing information around bought shares.
    """
    return Account.get(name).buy_shares(symbol, quantity, rationale)
    
@mcp.tool()
async def sell_shares(name: str, symbol: str, quantity: int, rationale: str) -> str:
    """
    Sell shares of a stock.

    Args:
        name: The name of the account holder
        symbol: The symbol of the stock
        quantity: The quantity of shares to sell
        rationale: The rationale for the sale and fit with the account's strategy.

    Returns:
        A string which contains information around sold shares.
    """
    return Account.get(name).sell_shares(symbol, quantity, rationale)
    
@mcp.tool()
async def change_strategy(name: str, strategy: str) -> str:
    """
    At your discretion, if you choose to, call this to change your investment strategy for the future.

    Args:
        name: The name of the account holder.
        strategy: The new strategy for the account
    
    Returns:
        A string confirming about the change in strategy.
    """

    return Account.get(name).change_strategy(strategy)

@mcp.resource("accounts://accounts_server/{name}")
async def read_account_resource(name: str) -> str:
    account = Account.get(name.lower())
    return account.report()

@mcp.resource("accounts://strategy/{name}")
async def read_strategy_resource(name: str) -> str:
    account = Account.get(name.lower())
    return account.get_strategy()

if __name__ == "__main__":
    mcp.run(transport="stdio")
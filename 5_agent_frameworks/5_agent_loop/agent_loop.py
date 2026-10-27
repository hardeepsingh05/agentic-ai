"""
The agent loop: a Google ADK orchestrator agent that runs the whole Week 5 team.

The orchestrator is itself an agent. Given the workers you built across the week and
a language to teach, it authors a shared look, hands each framework's worker a game
to build, launches them in parallel against one shared board, watches that board fill
in live, then plays each finished game in a real browser to check it and sends a
builder back to fix any that do not work. Open the printed index.html to play.

uv run agent_loop.py                        # A spansih arcade from every worker you have
uv run agent_loop.py --language French      # Any language
uv run agent_loop.py --skip agno            # Leave a framework out
uv run agent_loop.py --dry-run              # Show the plan without running the agent
uv run agent_loop.py --no-open              # Build it but do not open the browser at the end
"""

from __future__ import annotations

import argparse
import asyncio
import os 
import sys
from pathlib import Path

from dotenv import load_dotenv

## The orchestrator prints the agents' own words, which can include characters beyond the windows console's default code page (an emoji in a summary, for instance).
# Make stdout UTF-8 so that text renders rather than crushing the run on Windows.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv(override=True) # loading the environment variables

import config # noqa: E402  # imported after load_dotenv so it sees any model ids set in .env

HERE = Path(__file__).resolve().parent
SITE = HERE / "site"
BOARD_PATH = SITE / "board.sqlite"

# Point both the board and the workers at the shared site before board is imported, so every process in the run reads the one shared file and
# the workers use the chosen model. The workers inherit this environment when launched
os.environ["BOARD_PATH"] = str(BOARD_PATH)
if config.WORKER_MODEL:
    os.environ["WORKER_MODEL"] = config.WORKER_MODEL

import catalog # noqa: E402
import orchestrator # noqa: E402
import qa_agent # noqa: E402

def check_filesystem_server() -> None:
    """
    Exit with the start command unless filesystem_server.py is reachable and rooted at the shared site.

    The workers write their games through this server, so a server rooted anywhere else would
    leave every game missing from the site folder.

    Returns:
        None

    Raises:
        SystemExit: If the server cannot be reached at config.FILESYSTEM_MCP_URL, or its root folder is not the shared site.
    """
    from fastmcp import Client

    async def served_root() -> str:
        """
        Ask the running server for its root folder through its pwd tool.

        Returns:
            The root folder the server was started with.

        Raises:
            RuntimeError: If the server cannot be reached.
        """
        async with Client(config.FILESYSTEM_MCP_URL) as client:
            result = await client.call_tool("pwd")
            return result.content[0].text

    start = f'$env:MCP_ROOT = "{SITE}"; uvicorn filesystem_server:app --host 127.0.0.1 --port 8000'
    try:
        root = asyncio.run(served_root())
    except Exception as exc:
        raise SystemExit(
            f"Filesystem server not reachable at {config.FILESYSTEM_MCP_URL} ({type(exc).__name__}).\n"
            f"In another terminal, from {HERE}, run:\n  {start}"
        )
    if Path(root).resolve() != SITE.resolve():
        raise SystemExit(
            f"Filesystem server is rooted at {root}, but the games are built in {SITE}.\n"
            f"Stop it and restart it from {HERE} with:\n  {start}"
        )

def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments for the agent loop.

    Returns:
        argparse.Namespace: The parsed arguments: language, skip, dry_run and no_open.

    Raises:
        SystemExit: If an argument is not recognised (argparse prints the usage and exits).
    """
    parser = argparse.ArgumentParser(description="Build a language-game arcade with the week 5 team.")
    parser.add_argument("--language", default="Spanish", help="the language to learn for which games will be made (default: Spanish)")
    parser.add_argument("--skip", nargs="*", default=[], help="worker keys to leave out, e.g. --skip agno mastra")
    parser.add_argument("--dry-run", action="store_true", help="show the plan; do not run the agent")
    parser.add_argument("--no-open", action="store_true", help="do not open the finished site in a browser")
    return parser.parse_args()

def main() -> None:
    """
    Main function to run the agent loop.

    This function parses command-line arguments, discovers worker files, and orchestrates the building of a language-game arcade.
    It also performs a final check to ensure all games are built and optionally opens the finished site in a browser.

    Returns:
        None

    Raises:
        SystemExit: If a required setting is missing from .env, no worker files are found, or the filesystem server is
            not running at the shared site.
    """
    args = parse_args()
    config.check()
    workers = catalog.discover(skip=tuple(args.skip))
    if not workers:
        raise SystemExit("No worker files found. Build at least one framework's worker first.")

    print(f"Assembling a {args.language} arcade with {len(workers)} builders:")
    for worker in workers:
        print(f" {worker['name']:<28} -> folder {worker['slug']}/ (game invented at runtime)")
    if args.dry_run:
        print("\nDry run: stopping before the agent runs.")
        return
    
    check_filesystem_server()
    print(f"\n{config.ORCHESTRATOR_MODEL} is leading the team. Watch the board fill in:\n")
    orchestrator.run(
        args.language,
        workers,
        SITE,
        BOARD_PATH
    )

    # A final deterministic check, so a game the agent missed is still surfaced.
    print("\n Final check:")
    for worker in workers:
        slug=worker["slug"]
        built=orchestrator.is_built(SITE / slug)
        print(f"  {worker['name']:<28} {'OK' if built else 'INCOMPLETE'} ({slug})")
    
    index = SITE / "index.html"
    print("\n The team has finished. Open this to play:")
    print(f"    {index.resolve().as_uri()}")
    if not args.no_open:
        qa_agent.open_site(index)
    
if __name__ == "__main__":
    main()

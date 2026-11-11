"""
Browser MCP server: exposes BrowserTools (Playwright) as MCP tools over HTTP/SSE so any MCP-capable agent can browse the web.

Run (see the bottom of this file for the exact commands):
    uvicorn browser_server:app --host 127.0.0.1 --port 8001
The agent connects to http://127.0.0.1:8001/sse
"""

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, List, Optional

from fastapi import FastAPI

try:
    from mcp.server.mcpserver import MCPServer as FastMCP  # mcp 2.x
except ImportError:
    from mcp.server.fastmcp import FastMCP  # mcp 1.x

from browser_tools import BrowserTools

# Screenshots are written inside this folder, the same sandbox variable filesystem_server.py uses.
ROOT = Path(os.environ.get("MCP_ROOT", ".")).resolve()
HEADLESS = os.environ.get("BROWSER_HEADLESS", "true").lower() != "false"
# "chrome" uses the installed Chrome; set BROWSER_CHANNEL="" to use Playwright's bundled Chromium instead.
CHANNEL = os.environ.get("BROWSER_CHANNEL", "chrome") or None
TIMEOUT_MS = int(os.environ.get("BROWSER_TIMEOUT_MS", "15000"))

mcp = FastMCP("browser")

# Playwright's sync API is bound to the thread that started it, so one worker thread owns the browser
# and also serialises calls.
_thread = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mcp-browser")
_browser = BrowserTools(headless=HEADLESS, timeout=TIMEOUT_MS, channel=CHANNEL)


def _invoke(method: str, args: tuple, kwargs: dict) -> Any:
    """Run one BrowserTools method on the worker thread, launching the browser on first use."""
    if _browser.page is None:
        _browser.start()
    return getattr(_browser, method)(*args, **kwargs)


async def _call(method: str, *args: Any, **kwargs: Any) -> Any:
    """Run a BrowserTools method off the event loop; failures return as {"ok": False, "error": ...} for the agent to react to."""
    try:
        return await asyncio.get_running_loop().run_in_executor(_thread, _invoke, method, args, kwargs)
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:500]}"}


def _resolve(path: str) -> Path:
    """Resolve a path inside ROOT, rejecting anything that escapes it."""
    p = (ROOT / path).resolve()
    if p != ROOT and ROOT not in p.parents:
        raise ValueError("Access outside sandbox is not allowed.")
    return p


# ----------------------------------------------------
# Lifecycle / navigation
# ----------------------------------------------------

@mcp.tool()
async def browser_navigate(url: str, wait_until: str = "domcontentloaded") -> dict:
    """Open a URL. wait_until is one of commit, domcontentloaded, load, networkidle. Returns final url, title and HTTP status."""
    return await _call("browser_navigate", url, wait_until=wait_until)


@mcp.tool()
async def browser_navigate_back() -> dict:
    """Go back one page in the browser history."""
    return await _call("browser_navigate_back")


@mcp.tool()
async def browser_close() -> dict:
    """Close the browser. It reopens automatically on the next browser tool call."""
    if _browser.page is None:
        return {"ok": True, "message": "Browser was already closed."}
    return await _call("browser_close")


@mcp.tool()
async def browser_resize(width: int, height: int) -> dict:
    """Resize the viewport in pixels."""
    return await _call("browser_resize", width, height)


@mcp.tool()
async def browser_tabs(action: str = "list", index: Optional[int] = None, url: Optional[str] = None) -> Any:
    """List, open, switch or close tabs. action is list, new, switch or close; index selects a tab; url is opened in a new tab."""
    return await _call("browser_tabs", action=action, index=index, url=url)


# ----------------------------------------------------
# Reading the page
# ----------------------------------------------------

@mcp.tool()
async def browser_snapshot(max_chars: int = 8000) -> dict:
    """Compact view of the current page: url, title, visible text, and its headings, links, buttons and inputs. Call after each action."""
    return await _call("browser_snapshot", max_chars=max_chars)


@mcp.tool()
async def browser_get_text(target: str, by: str = "css", all_matches: bool = False) -> Any:
    """Read the visible text of an element (or of every match when all_matches is true)."""
    return await _call("get_text", target, by=by, all_matches=all_matches)


@mcp.tool()
async def browser_extract_links(limit: int = 100) -> Any:
    """List up to `limit` links ({text, href}) on the current page."""
    return await _call("extract_links", limit=limit)


@mcp.tool()
async def browser_find(target: str, by: str = "text") -> dict:
    """Check whether an element exists. by is css, role ("button:Submit"), text, label, placeholder or testid."""
    return await _call("browser_find", target, by=by)


@mcp.tool()
async def browser_evaluate(javascript: str) -> Any:
    """Run a JavaScript function or expression in the page, such as "() => document.title", and return its JSON result."""
    return {"result": await _call("browser_evaluate", javascript)}


@mcp.tool()
async def browser_console_messages(clear: bool = False) -> Any:
    """Console messages and uncaught page errors captured so far."""
    return {"messages": await _call("browser_console_messages", clear=clear)}


@mcp.tool()
async def browser_network_requests(contains: Optional[str] = None, clear: bool = False) -> Any:
    """Network requests made by the page so far, optionally only those whose URL contains `contains`."""
    return {"requests": await _call("browser_network_requests", contains=contains, clear=clear)}


@mcp.tool()
async def browser_take_screenshot(path: str = "screenshot.png", full_page: bool = True) -> dict:
    """Save a screenshot inside the sandbox folder and return its relative path."""
    try:
        target = _resolve(path)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    target.parent.mkdir(parents=True, exist_ok=True)
    result = await _call("browser_take_screenshot", str(target), full_page=full_page)
    if isinstance(result, dict):
        return result
    return {"ok": True, "path": str(target.relative_to(ROOT))}


# ----------------------------------------------------
# Interacting with the page
# ----------------------------------------------------

@mcp.tool()
async def browser_click(target: str, by: str = "css") -> dict:
    """Click an element. Prefer a CSS selector or by="role" with "button:Name"; by="text" matches any element containing the words."""
    return await _call("browser_click", target, by=by)


@mcp.tool()
async def browser_hover(target: str, by: str = "css") -> dict:
    """Move the mouse over an element."""
    return await _call("browser_hover", target, by=by)


@mcp.tool()
async def browser_type(target: str, text: str, by: str = "css", delay: int = 0) -> dict:
    """Type text into an element one key at a time; delay is milliseconds between key presses."""
    return await _call("browser_type", target, text, by=by, delay=delay)


@mcp.tool()
async def browser_press_key(key: str, target: str = "", by: str = "css") -> dict:
    """Press a key such as Enter, Escape, Tab or Control+A, on an element or (when target is empty) the page."""
    return await _call("browser_press_key", key, target=target or None, by=by)


@mcp.tool()
async def browser_select_option(target: str, value: str, by: str = "css") -> Any:
    """Choose an option (by its value attribute) in a select dropdown."""
    return await _call("browser_select_option", target, value, by=by)


@mcp.tool()
async def browser_fill_form(fields: List[dict]) -> Any:
    """Fill several fields. Each field is {"target", "value", "by" (default css), "type" (text, select or check)}."""
    return await _call("browser_fill_form", fields)


@mcp.tool()
async def browser_drag(source: str, target: str, source_by: str = "css", target_by: str = "css") -> dict:
    """Drag one element onto another."""
    return await _call("browser_drag", source, target, source_by, target_by)


@mcp.tool()
async def browser_wait_for(target: str = "", by: str = "css", state: str = "visible", seconds: float = 0.0) -> dict:
    """Wait for an element to reach a state (attached, detached, visible, hidden), or wait `seconds` when no target is given."""
    return await _call("browser_wait_for", target=target or None, by=by, state=state, seconds=seconds or None)


@mcp.tool()
async def browser_handle_dialog(accept: bool = True, prompt_text: str = "") -> dict:
    """Accept or dismiss an alert, confirm or prompt dialog the page opened."""
    return await _call("browser_handle_dialog", accept=accept, prompt_text=prompt_text)


app = FastAPI()

# Mount MCP over HTTP/SSE; the agent connects to /sse
app.mount("/", mcp.sse_app())

# Run in a terminal from this folder (PowerShell), using the same Python as the notebook:
#   $env:MCP_ROOT="<path to your sandbox folder>"
#   uvicorn browser_server:app --host 127.0.0.1 --port 8001
# Optional: $env:BROWSER_HEADLESS="false" to watch the browser; $env:BROWSER_CHANNEL="" for bundled Chromium.

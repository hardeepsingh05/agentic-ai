"""
The QA agent's browser tools: BrowserTools (Playwright) exposed as async ADK tools.

Playwright's sync API cannot run on the asyncio loop and its objects must stay on the thread that
created them, so each BrowserSession owns one worker thread and hands every call to it. One session
per QA check keeps concurrent checks from sharing a page.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from browser_tools import BrowserTools


class BrowserSession:
    """
    One QA check's browser: a Chrome window driven through BrowserTools on its own worker thread.

    The browser opens on the first tool call and is closed with close(). The tool methods are async so ADK can
    await them, and they never raise: a failed action comes back as an error result for the agent to react to.
    """

    def __init__(self, headless: bool = False, timeout: int = 15000) -> None:
        """
        Prepare a session; Chrome is not started until the first tool call.

        Args:
            headless: True to hide the browser window.
            timeout: Milliseconds Playwright waits for each action before giving up.
        """
        # The installed Chrome is used because Playwright's bundled Chromium is not installed here.
        self._browser = BrowserTools(headless=headless, timeout=timeout, channel="chrome")
        self._thread = ThreadPoolExecutor(max_workers=1, thread_name_prefix="qa-browser")

    def _invoke(self, method: str, args: tuple, kwargs: dict) -> Any:
        """
        Run one BrowserTools method on the worker thread, starting the browser first if needed.

        Args:
            method: Name of the BrowserTools method to call.
            args: Its positional arguments.
            kwargs: Its keyword arguments.

        Returns:
            Whatever the BrowserTools method returns.

        Raises:
            playwright.sync_api.Error: If Chrome cannot be started or the action fails.
            AttributeError: If BrowserTools has no method of that name.
        """
        # Runs on the worker thread; being the only thread, it also serialises calls and starts the browser once.
        if self._browser.page is None:
            self._browser.start()
        return getattr(self._browser, method)(*args, **kwargs)

    async def _call(self, method: str, *args: Any, **kwargs: Any) -> Any:
        """
        Hand a BrowserTools call to the worker thread and wait for it without blocking the event loop.

        Args:
            method: Name of the BrowserTools method to call.
            *args: Its positional arguments.
            **kwargs: Its keyword arguments.

        Returns:
            The method's result, or {"ok": False, "error": "<type>: <message>"} if it failed.

        Raises:
            None: every exception is caught and returned as an error result.
        """
        try:
            return await asyncio.get_running_loop().run_in_executor(self._thread, self._invoke, method, args, kwargs)
        except Exception as exc:
            # A failed action is a result for the agent to react to, not a reason to abort the whole check.
            return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:500]}"}

    async def close(self) -> None:
        """
        Close the browser if it was opened, then stop the worker thread.

        Returns:
            None

        Raises:
            playwright.sync_api.Error: If the browser fails while closing. The worker thread is stopped regardless.
        """
        try:
            if self._browser.page is not None:
                await asyncio.get_running_loop().run_in_executor(self._thread, self._browser.browser_close)
        finally:
            self._thread.shutdown(wait=False)

    def tools(self) -> list:
        """
        The browser tools to hand to the QA agent.

        Returns:
            The eleven async tool methods: navigate, snapshot, find, click, type, press_key, drag, wait_for,
            evaluate, console_messages and handle_dialog.
        """
        return [
            self.browser_navigate,
            self.browser_snapshot,
            self.browser_find,
            self.browser_click,
            self.browser_type,
            self.browser_press_key,
            self.browser_drag,
            self.browser_wait_for,
            self.browser_evaluate,
            self.browser_console_messages,
            self.browser_handle_dialog,
        ]

    async def browser_navigate(self, url: str) -> dict:
        """
        Open a URL in the browser.

        Args:
            url: Full address to open, such as a file:// address.

        Returns:
            The final URL, page title and HTTP status.

        Raises:
            None: a failure comes back as an error result such as {"ok": False, "error": ...} so you can adapt.
        """
        return await self._call("browser_navigate", url)

    async def browser_snapshot(self, max_chars: int = 6000) -> dict:
        """
        Compact view of the current page: title, visible text, and its headings, links, buttons and inputs.
        Take one after each action to see what changed.

        Args:
            max_chars: Maximum amount of visible page text to return.

        Returns:
            The page snapshot.

        Raises:
            None: a failure comes back as an error result such as {"ok": False, "error": ...} so you can adapt.
        """
        return await self._call("browser_snapshot", max_chars=max_chars)

    async def browser_find(self, target: str, by: str = "text") -> dict:
        """
        Check whether an element exists on the page.

        Args:
            target: A CSS selector such as "#startBtn", or "role:name" such as "button:Start Game". Prefer these: with by="text"
                any element containing the words matches, including a sentence that merely mentions them.
            by: How to locate it: css, role, text, label, placeholder or testid.

        Returns:
            Whether it was found, how many matched, and the first match's text.

        Raises:
            None: a failure comes back as an error result such as {"ok": False, "error": ...} so you can adapt.
        """
        return await self._call("browser_find", target, by=by)

    async def browser_click(self, target: str, by: str = "css") -> dict:
        """
        Click an element on the page.

        Args:
            target: A CSS selector such as "#startBtn" (ids are listed in the snapshot), or "role:name" such as "button:Start Game".
                Prefer these: with by="text" any element containing the words matches, including a sentence that merely mentions them.
            by: How to locate it: css, role, text, label, placeholder or testid.

        Returns:
            A dictionary saying whether the click worked.

        Raises:
            None: a failure, such as clicking a disabled button, comes back as {"ok": False, "error": ...} so you can adapt.
        """
        return await self._call("browser_click", target, by=by)

    async def browser_type(self, target: str, text: str, by: str = "css") -> dict:
        """
        Type text into an input or other editable element.

        Args:
            target: Locator of the element.
            text: The text to type.
            by: How to locate it: css, text, label, placeholder, testid or role.

        Returns:
            A dictionary saying whether typing worked.

        Raises:
            None: a failure comes back as an error result such as {"ok": False, "error": ...} so you can adapt.
        """
        return await self._call("browser_type", target, text, by=by)

    async def browser_press_key(self, key: str, target: str = "", by: str = "css") -> dict:
        """
        Press a keyboard key, on one element or on the page as a whole.

        Args:
            key: Key name, such as Enter, Escape, Tab, ArrowDown or Control+A.
            target: Optional locator of the element to press it on; leave empty for the page.
            by: How to locate the target.

        Returns:
            A dictionary saying whether the key press worked.

        Raises:
            None: a failure comes back as an error result such as {"ok": False, "error": ...} so you can adapt.
        """
        return await self._call("browser_press_key", key, target=target or None, by=by)

    async def browser_drag(self, source: str, target: str, source_by: str = "css", target_by: str = "css") -> dict:
        """
        Drag one element onto another.

        Args:
            source: Locator of the element to drag.
            target: Locator of the element to drop it on.
            source_by: How to locate the source.
            target_by: How to locate the target.

        Returns:
            A dictionary saying whether the drag worked.

        Raises:
            None: a failure comes back as an error result such as {"ok": False, "error": ...} so you can adapt.
        """
        return await self._call("browser_drag", source, target, source_by, target_by)

    async def browser_wait_for(self, target: str = "", by: str = "css", seconds: float = 0.0) -> dict:
        """
        Wait for an element to become visible, or just wait a number of seconds.

        Args:
            target: Locator of the element to wait for; leave empty to wait a fixed time.
            by: How to locate the target.
            seconds: Seconds to wait when no target is given.

        Returns:
            A dictionary saying whether the wait finished.

        Raises:
            None: a timeout or other failure comes back as {"ok": False, "error": ...} so you can adapt.
        """
        return await self._call("browser_wait_for", target=target or None, by=by, seconds=seconds or None)

    async def browser_evaluate(self, javascript: str) -> dict:
        """
        Run JavaScript in the page and return its result, for reading page or game state.

        Args:
            javascript: A JavaScript expression or function, such as "() => document.title".

        Returns:
            The JSON-serialisable result under "result".

        Raises:
            None: a JavaScript error comes back under "result" as {"ok": False, "error": ...} so you can adapt.
        """
        return {"result": await self._call("browser_evaluate", javascript)}

    async def browser_console_messages(self, clear: bool = False) -> dict:
        """
        The page's console messages and uncaught errors so far; errors have type "error" or "pageerror".

        Args:
            clear: Clear the stored messages after returning them.

        Returns:
            The messages under "messages".

        Raises:
            None: a failure comes back under "messages" as {"ok": False, "error": ...}.
        """
        return {"messages": await self._call("browser_console_messages", clear=clear)}

    async def browser_handle_dialog(self, accept: bool = True) -> dict:
        """
        Accept or dismiss an alert, confirm or prompt dialog the page opened.

        Args:
            accept: True to accept it, False to dismiss it.

        Returns:
            The dialog's message, or a note that none was open.

        Raises:
            None: a failure comes back as an error result such as {"ok": False, "error": ...} so you can adapt.
        """
        return await self._call("browser_handle_dialog", accept=accept)

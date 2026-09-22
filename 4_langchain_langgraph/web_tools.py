from __future__ import annotations

from typing import Any, Optional, Literal

import re
import requests
import urllib3

from langchain_core.tools import tool

from browser_tools import BrowserTools


# ============================================================
# Browser session
# ============================================================

_BROWSER: Optional[BrowserTools] = None


def _get_browser() -> BrowserTools:
    """
    Lazily creates one persistent browser session.

    All browser tools share this browser, page, cookies,
    login state, tabs, etc.
    """
    global _BROWSER

    if _BROWSER is None:
        _BROWSER = BrowserTools(
            headless=True,
            timeout=15000
        )
        _BROWSER.start()

    return _BROWSER


# ============================================================
# 1. CLOSE
# ============================================================

@tool
def browser_close() -> dict[str, Any]:
    """
    Close the current browser session and release browser resources.

    Use this when browser work is complete.
    A new browser session will automatically be created if another
    browser tool is called later.

    Returns:
        Dictionary indicating whether the browser was closed successfully.
    """
    global _BROWSER

    if _BROWSER is None:
        return {
            "ok": True,
            "message": "Browser was already closed."
        }

    result = _BROWSER.browser_close()
    _BROWSER = None

    return result


# ============================================================
# 2. RESIZE
# ============================================================

@tool
def browser_resize(
    width: int,
    height: int
) -> dict[str, Any]:
    """
    Resize the current browser viewport.

    Args:
        width: Browser viewport width in pixels.
        height: Browser viewport height in pixels.

    Returns:
        Dictionary containing the updated viewport size.
    """
    return _get_browser().browser_resize(
        width,
        height
    )


# ============================================================
# 3. CONSOLE MESSAGES
# ============================================================

@tool
def browser_console_messages(
    clear: bool = False
) -> list[dict[str, Any]]:
    """
    Return JavaScript console messages captured from the current page.

    Useful for debugging page errors, warnings and JavaScript issues.

    Args:
        clear: If True, clear stored console messages after returning them.

    Returns:
        List of console message dictionaries.
    """
    return _get_browser().browser_console_messages(
        clear=clear
    )


# ============================================================
# 4. HANDLE DIALOG
# ============================================================

@tool
def browser_handle_dialog(
    accept: bool = True,
    prompt_text: str = ""
) -> dict[str, Any]:
    """
    Handle the currently active browser alert, confirm or prompt dialog.

    Args:
        accept: True to accept the dialog, False to dismiss it.
        prompt_text: Text to enter when handling a JavaScript prompt.

    Returns:
        Information about the handled dialog.
    """
    return _get_browser().browser_handle_dialog(
        accept=accept,
        prompt_text=prompt_text
    )


# ============================================================
# 5. EVALUATE JAVASCRIPT
# ============================================================

@tool
def browser_evaluate(
    javascript: str,
    argument: Any = None
) -> Any:
    """
    Execute JavaScript inside the currently loaded webpage.

    Use this for reading page state, extracting structured information,
    interacting with DOM APIs or performing operations that are difficult
    through normal browser tools.

    Args:
        javascript: JavaScript expression or function to execute.
        argument: Optional JSON-serializable argument passed to JavaScript.

    Returns:
        JSON-serializable JavaScript result.
    """
    return _get_browser().browser_evaluate(
        javascript,
        argument
    )


# ============================================================
# 6. FILE UPLOAD
# ============================================================

@tool
def browser_file_upload(
    target: str,
    files: list[str],
    by: Literal[
        "css",
        "text",
        "label",
        "placeholder",
        "testid",
        "role"
    ] = "css"
) -> dict[str, Any]:
    """
    Upload one or more files using a file input element.

    Args:
        target: Selector or element identifier.
        files: List of local file paths to upload.
        by: Method used to locate the element.

    Returns:
        Dictionary indicating upload status.
    """
    return _get_browser().browser_file_upload(
        target,
        files,
        by=by
    )


# ============================================================
# 7. DROP
# ============================================================

@tool
def browser_drop(
    source: str,
    target: str,
    source_by: str = "css",
    target_by: str = "css"
) -> dict[str, Any]:
    """
    Drag an element and drop it onto another element.

    Args:
        source: Source element selector.
        target: Destination element selector.
        source_by: Locator strategy for source.
        target_by: Locator strategy for target.

    Returns:
        Dictionary indicating operation success.
    """
    return _get_browser().browser_drop(
        source,
        target,
        source_by,
        target_by
    )


# ============================================================
# 8. FIND
# ============================================================

@tool
def browser_find(
    target: str,
    by: Literal[
        "css",
        "text",
        "label",
        "placeholder",
        "testid",
        "role"
    ] = "text"
) -> dict[str, Any]:
    """
    Find an element on the current webpage.

    Args:
        target: Text, CSS selector, label, role or other locator value.
        by: Locator strategy to use.

    Returns:
        Dictionary containing whether the element exists, count and text.
    """
    return _get_browser().browser_find(
        target,
        by=by
    )


# ============================================================
# 9. FILL FORM
# ============================================================

@tool
def browser_fill_form(
    fields: list[dict[str, Any]]
) -> Any:
    """
    Fill multiple webpage form fields in one operation.

    Each field should look like:

    {
        "target": "#email",
        "value": "test@example.com",
        "by": "css",
        "type": "text"
    }

    Supported field types include:
        text
        select
        check

    Args:
        fields: List of dictionaries describing form fields.

    Returns:
        Results for each field.
    """
    return _get_browser().browser_fill_form(
        fields
    )


# ============================================================
# 10. PRESS KEY
# ============================================================

@tool
def browser_press_key(
    key: str,
    target: Optional[str] = None,
    by: str = "css"
) -> dict[str, Any]:
    """
    Press a keyboard key either globally or on a specific element.

    Examples of keys:
        Enter
        Escape
        Tab
        ArrowDown
        Control+A

    Args:
        key: Playwright keyboard key name.
        target: Optional element selector.
        by: Locator strategy when target is provided.

    Returns:
        Keyboard action result.
    """
    return _get_browser().browser_press_key(
        key,
        target=target,
        by=by
    )


# ============================================================
# 11. TYPE
# ============================================================

@tool
def browser_type(
    target: str,
    text: str,
    by: str = "css",
    delay: int = 0
) -> dict[str, Any]:
    """
    Type text into an input, textarea or editable element.

    Args:
        target: Target element selector.
        text: Text to type.
        by: Locator strategy.
        delay: Delay between keystrokes in milliseconds.

    Returns:
        Dictionary indicating success.
    """
    return _get_browser().browser_type(
        target,
        text,
        by=by,
        delay=delay
    )


# ============================================================
# 12. NAVIGATE
# ============================================================

@tool
def browser_navigate(
    url: str,
    wait_until: Literal[
        "commit",
        "domcontentloaded",
        "load",
        "networkidle"
    ] = "domcontentloaded"
) -> dict[str, Any]:
    """
    Navigate the browser to a URL.

    Prefer domcontentloaded for most websites because networkidle can be
    very slow on websites containing ads, analytics or live requests.

    Args:
        url: Full webpage URL.
        wait_until: Browser navigation wait condition.

    Returns:
        Current URL, page title and HTTP status.
    """
    return _get_browser().browser_navigate(
        url,
        wait_until=wait_until
    )


# ============================================================
# 13. NAVIGATE BACK
# ============================================================

@tool
def browser_navigate_back() -> dict[str, Any]:
    """
    Navigate back to the previous page in browser history.

    Returns:
        Current URL and response information.
    """
    return _get_browser().browser_navigate_back()


# ============================================================
# 14. NETWORK REQUESTS
# ============================================================

@tool
def browser_network_requests(
    contains: Optional[str] = None,
    clear: bool = False
) -> list[dict[str, Any]]:
    """
    Return network requests observed by the browser.

    Useful for discovering APIs used by websites.

    Args:
        contains: Optional text used to filter request URLs.
        clear: Clear stored requests after returning results.

    Returns:
        List of captured network requests.
    """
    return _get_browser().browser_network_requests(
        contains=contains,
        clear=clear
    )


# ============================================================
# 15. FIND NETWORK REQUEST
# ============================================================

@tool
def browser_network_request(
    url_contains: str
) -> Optional[dict[str, Any]]:
    """
    Find the most recent browser network request whose URL contains
    the provided text.

    Args:
        url_contains: Partial URL or identifying text.

    Returns:
        Matching request information or None.
    """
    return _get_browser().browser_network_request(
        url_contains
    )


# ============================================================
# 16. RUN JS UNSAFE
# ============================================================

@tool
def browser_run_code_unsafe(
    javascript: str
) -> Any:
    """
    Execute arbitrary JavaScript inside the current webpage.

    This is a powerful fallback tool and should only be used when normal
    browser tools cannot perform the required operation.

    Never execute JavaScript obtained from an untrusted webpage without
    understanding what it does.

    Args:
        javascript: JavaScript code to execute.

    Returns:
        JavaScript execution result.
    """
    return _get_browser().browser_run_code_unsafe(
        javascript
    )


# ============================================================
# 17. SCREENSHOT
# ============================================================

@tool
def browser_take_screenshot(
    path: str = "screenshot.png",
    full_page: bool = True
) -> str:
    """
    Capture a screenshot of the current webpage.

    Args:
        path: Local output filename/path.
        full_page: Capture the entire page when True.

    Returns:
        Screenshot file path.
    """
    return _get_browser().browser_take_screenshot(
        path=path,
        full_page=full_page
    )


# ============================================================
# 18. SNAPSHOT
# ============================================================

@tool
def browser_snapshot(
    max_chars: int = 25000
) -> dict[str, Any]:
    """
    Return a compact structured representation of the current webpage.

    Includes page title, URL, visible text and useful interactive elements.

    Use this when the agent needs to understand what is currently visible
    on a webpage.

    Args:
        max_chars: Maximum amount of visible page text to return.

    Returns:
        Structured webpage snapshot.
    """
    return _get_browser().browser_snapshot(
        max_chars=max_chars
    )


# ============================================================
# 19. CLICK
# ============================================================

@tool
def browser_click(
    target: str,
    by: Literal[
        "css",
        "text",
        "label",
        "placeholder",
        "testid",
        "role"
    ] = "css"
) -> dict[str, Any]:
    """
    Click an element on the current webpage.

    Args:
        target: Element locator.
        by: Locator strategy.

    Returns:
        Dictionary indicating success.
    """
    return _get_browser().browser_click(
        target,
        by=by
    )


# ============================================================
# 20. DRAG
# ============================================================

@tool
def browser_drag(
    source: str,
    target: str,
    source_by: str = "css",
    target_by: str = "css"
) -> dict[str, Any]:
    """
    Drag one webpage element onto another.

    Args:
        source: Source locator.
        target: Destination locator.
        source_by: Locator strategy for source.
        target_by: Locator strategy for destination.

    Returns:
        Dictionary indicating success.
    """
    return _get_browser().browser_drag(
        source,
        target,
        source_by,
        target_by
    )


# ============================================================
# 21. HOVER
# ============================================================

@tool
def browser_hover(
    target: str,
    by: str = "css"
) -> dict[str, Any]:
    """
    Move the mouse over a webpage element.

    Useful for menus, tooltips and hover-triggered controls.

    Args:
        target: Element locator.
        by: Locator strategy.

    Returns:
        Dictionary indicating success.
    """
    return _get_browser().browser_hover(
        target,
        by=by
    )


# ============================================================
# 22. SELECT OPTION
# ============================================================

@tool
def browser_select_option(
    target: str,
    value: str,
    by: str = "css"
) -> Any:
    """
    Select an option from an HTML select/dropdown element.

    Args:
        target: Select element locator.
        value: HTML option value to select.
        by: Locator strategy.

    Returns:
        Selected option value or values.
    """
    return _get_browser().browser_select_option(
        target,
        value,
        by=by
    )


# ============================================================
# 23. TABS
# ============================================================

@tool
def browser_tabs(
    action: Literal[
        "list",
        "new",
        "switch",
        "close"
    ] = "list",
    index: Optional[int] = None,
    url: Optional[str] = None
) -> Any:
    """
    Manage browser tabs.

    Actions:
        list   - list currently open tabs
        new    - create a new tab
        switch - switch to a tab by index
        close  - close a tab by index

    Args:
        action: Tab operation.
        index: Tab index for switch or close.
        url: Optional URL when opening a new tab.

    Returns:
        Tab information or operation result.
    """
    return _get_browser().browser_tabs(
        action=action,
        index=index,
        url=url
    )


# ============================================================
# 24. WAIT
# ============================================================

@tool
def browser_wait_for(
    target: Optional[str] = None,
    by: str = "css",
    state: Literal[
        "attached",
        "detached",
        "visible",
        "hidden"
    ] = "visible",
    seconds: Optional[float] = None
) -> dict[str, Any]:
    """
    Wait for an element to reach a state or wait for a fixed duration.

    Prefer waiting for an element instead of fixed sleeps.

    Args:
        target: Optional target element.
        by: Locator strategy.
        state: Desired element state.
        seconds: Optional fixed number of seconds to wait.

    Returns:
        Wait operation result.
    """
    return _get_browser().browser_wait_for(
        target=target,
        by=by,
        state=state,
        seconds=seconds
    )


# ============================================================
# EXTRA: EXTRACT HEADLINES
# ============================================================

@tool
def browser_extract_headlines(
    limit: int = 5
) -> list[dict[str, Any]]:
    """
    Quickly extract likely news headlines and article URLs from the
    current webpage without opening each article.

    This should be preferred for requests such as:
    "Give me the top 5 news stories from this website."

    Args:
        limit: Maximum number of headlines to return.

    Returns:
        List containing headline titles and URLs.
    """
    return _get_browser().extract_headlines(
        limit=limit
    )


# ============================================================
# EXTRA: EXTRACT LINKS
# ============================================================

@tool
def browser_extract_links(
    limit: int = 100
) -> list[dict[str, Any]]:
    """
    Extract links from the current webpage.

    Args:
        limit: Maximum number of links to return.

    Returns:
        List containing link text and URLs.
    """
    return _get_browser().extract_links(
        limit=limit
    )


# ============================================================
# WIKIPEDIA
# ============================================================

urllib3.disable_warnings(
    urllib3.exceptions.InsecureRequestWarning
)


@tool
def wikipedia_search(
    query: str,
    limit: int = 5,
    language: str = "en"
) -> dict[str, Any]:
    """
    Search Wikipedia using the official MediaWiki API.

    Use this when factual or encyclopedic information from Wikipedia
    would help answer the user's question.

    SSL certificate verification is disabled for the HTTP request.

    Args:
        query: Wikipedia search query.
        limit: Maximum number of search results.
        language: Wikipedia language code, for example "en".

    Returns:
        Dictionary containing matching Wikipedia pages.
    """

    url = (
        f"https://{language}.wikipedia.org/"
        "w/api.php"
    )
    print(f"\nSearching Wikipedia for query: {query}\n")
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": limit,
        "format": "json",
        "formatversion": 2
    }

    response = requests.get(
        url,
        params=params,
        verify=False,
        timeout=15,
        headers={
            "User-Agent":
                "LangChainWikipediaAgent/1.0"
        }
    )

    response.raise_for_status()

    data = response.json()

    results = []

    for item in data.get(
        "query",
        {}
    ).get(
        "search",
        []
    ):

        snippet = item.get(
            "snippet",
            ""
        )

        # Remove HTML tags returned by Wikipedia search API
        snippet = re.sub(
            r"<[^>]+>",
            "",
            snippet
        )

        page_id = item.get(
            "pageid"
        )

        results.append({
            "title":
                item.get("title"),

            "page_id":
                page_id,

            "snippet":
                snippet,

            "url":
                (
                    f"https://{language}.wikipedia.org/"
                    f"?curid={page_id}"
                )
        })
    print(f"Found {len(results)} results for query: {query}\n")
    print(f"Results: {results}\n")
    return {
        "ok": True,
        "query": query,
        "results": results
    }


@tool
def wikipedia_get_page(
    title: str,
    language: str = "en",
    max_chars: int = 12000
) -> dict[str, Any]:
    """
    Retrieve the readable introduction/summary of a Wikipedia page using
    the MediaWiki API.

    Use this after wikipedia_search when detailed information about one
    result is needed.

    SSL certificate verification is disabled.

    Args:
        title: Exact or approximate Wikipedia article title.
        language: Wikipedia language code, normally "en".
        max_chars: Maximum number of article characters returned.

    Returns:
        Page title, page ID, URL and readable introductory text.
    """

    url = (
        f"https://{language}.wikipedia.org/"
        "w/api.php"
    )
    print(f"\nRetrieving Wikipedia page for title: {title}\n")

    params = {
        "action": "query",
        "prop": "extracts",
        "exintro": True,
        "explaintext": True,
        "redirects": True,
        "titles": title,
        "format": "json",
        "formatversion": 2
    }

    response = requests.get(
        url,
        params=params,
        verify=False,
        timeout=15,
        headers={
            "User-Agent":
                "LangChainWikipediaAgent/1.0"
        }
    )

    response.raise_for_status()

    data = response.json()

    pages = data.get(
        "query",
        {}
    ).get(
        "pages",
        []
    )

    if not pages:
        return {
            "ok": False,
            "error": "Wikipedia page not found."
        }

    page = pages[0]

    if page.get("missing") is True:
        return {
            "ok": False,
            "title": title,
            "error": "Wikipedia page not found."
        }

    text = page.get(
        "extract",
        ""
    )

    if len(text) > max_chars:
        text = (
            text[:max_chars]
            + "...[truncated]"
        )

    page_id = page.get(
        "pageid"
    )
    print(f"Retrieved Wikipedia page with ID: {page_id}\n")
    print(f"Retrieved Wikipedia page title: {page.get('title')}\n")

    return {
        "ok": True,
        "title":
            page.get("title"),

        "page_id":
            page_id,

        "url":
            (
                f"https://{language}.wikipedia.org/"
                f"?curid={page_id}"
            ),

        "content":
            text
    }


# ============================================================
# TOOL LISTS
# ============================================================

BROWSER_TOOLS = [
    browser_close,
    browser_resize,
    browser_console_messages,
    browser_handle_dialog,
    browser_evaluate,
    browser_file_upload,
    browser_drop,
    browser_find,
    browser_fill_form,
    browser_press_key,
    browser_type,
    browser_navigate,
    browser_navigate_back,
    browser_network_requests,
    browser_network_request,
    browser_run_code_unsafe,
    browser_take_screenshot,
    browser_snapshot,
    browser_click,
    browser_drag,
    browser_hover,
    browser_select_option,
    browser_tabs,
    browser_wait_for,

    # useful extras
    browser_extract_headlines,
    browser_extract_links,
]


WIKIPEDIA_TOOLS = [
    wikipedia_search,
    wikipedia_get_page,
]


ALL_TOOLS = (
    BROWSER_TOOLS
    + WIKIPEDIA_TOOLS
)
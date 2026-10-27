from playwright.sync_api import sync_playwright
import time


class BrowserTools:
    """
    A small Playwright (sync API) wrapper that gives an agent a browser: navigate, find, click, type, read the page,
    and watch the console and network.

    Playwright's sync API must be used from one thread that is not running an asyncio loop, and every method here
    raises Playwright's own errors (playwright.sync_api.Error, or TimeoutError for a timeout) when an action fails.
    web_tools.BrowserSession takes care of both for the async agents.

    Attributes:
        headless: Whether the browser window is hidden.
        timeout: Milliseconds Playwright waits for an action or navigation before timing out.
        channel: An installed browser to use, such as "chrome"; None uses Playwright's bundled Chromium.
        console_logs: Console messages and page errors captured so far.
        requests: Network requests captured so far.
        dialog: The alert, confirm or prompt dialog currently waiting to be handled, if any.
    """

    def __init__(self, headless=True, timeout=15000, channel=None):
        """
        Store the browser settings; nothing is launched until start() is called.

        Args:
            headless: True to hide the browser window.
            timeout: Milliseconds Playwright waits for an action or navigation before timing out.
            channel: An installed browser to launch, such as "chrome"; None uses Playwright's bundled Chromium.
        """
        self.headless = headless
        self.timeout = timeout
        self.channel = channel  # e.g. "chrome" to use the installed Chrome instead of Playwright's Chromium

        self.pw = None
        self.browser = None
        self.context = None
        self.page = None

        self.console_logs = []
        self.requests = []
        self.dialog = None

    def start(self):
        """
        Launch the browser and open one page, recording its console messages, page errors, requests and dialogs.

        Returns:
            This BrowserTools instance, so calls can be chained.

        Raises:
            playwright.sync_api.Error: If the browser cannot be launched (for example the chosen channel is not installed),
                or if called from inside a running asyncio loop, which Playwright's sync API does not allow.
        """
        self.pw = sync_playwright().start()

        self.browser = self.pw.chromium.launch(
            headless=self.headless,
            channel=self.channel
        )

        self.context = self.browser.new_context(
            viewport={"width": 1440, "height": 900}
        )

        self.page = self.context.new_page()

        self.page.set_default_timeout(self.timeout)
        self.page.set_default_navigation_timeout(self.timeout)

        self.page.on(
            "console",
            lambda msg: self.console_logs.append({
                "type": msg.type,
                "text": msg.text
            })
        )

        self.page.on(
            "pageerror",
            lambda err: self.console_logs.append({
                "type": "pageerror",
                "text": str(err)
            })
        )

        self.page.on(
            "request",
            lambda req: self.requests.append({
                "url": req.url,
                "method": req.method,
                "resource_type": req.resource_type
            })
        )

        self.page.on(
            "dialog",
            lambda dialog: setattr(self, "dialog", dialog)
        )

        return self

    def _page(self):
        """
        The current page.

        Returns:
            The Playwright page the tools act on.

        Raises:
            RuntimeError: If the browser has not been started.
        """
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")
        return self.page

    def _locator(self, target, by="css"):
        """
        Turn a target and a locator strategy into a Playwright locator.

        Args:
            target: The selector, text, label, placeholder, test id, or "role:name" such as "button:Submit".
            by: The strategy: css, text, label, placeholder, testid or role. Anything else is treated as css. Text matches
                prefer an exact match and only visible elements, so prose that merely mentions the text is skipped.

        Returns:
            A Playwright Locator.

        Raises:
            RuntimeError: If the browser has not been started.
            ValueError: If by is "role" and target has no "role:name" colon.
        """
        page = self._page()

        if by == "css":
            return page.locator(target)

        if by == "text":
            # Substring matching alone lands on prose or hidden copies of the text (e.g. "Press Start to begin" above
            # the Start button), so prefer an exact match and only visible elements.
            exact = page.get_by_text(target, exact=True).filter(visible=True)
            if exact.count():
                return exact

            return page.get_by_text(target).filter(visible=True)

        if by == "label":
            return page.get_by_label(target)

        if by == "placeholder":
            return page.get_by_placeholder(target)

        if by == "testid":
            return page.get_by_test_id(target)

        if by == "role":
            # Example:
            # target="button:Submit"
            role, name = target.split(":", 1)

            return page.get_by_role(
                role.strip(),
                name=name.strip()
            )

        return page.locator(target)

    # ----------------------------------------------------
    # Browser lifecycle
    # ----------------------------------------------------

    def browser_close(self):
        """
        Close the page, browser and Playwright, and forget them. Safe to call when nothing is open.

        Returns:
            {"ok": True}

        Raises:
            playwright.sync_api.Error: If the browser fails while closing.
        """
        if self.context:
            self.context.close()

        if self.browser:
            self.browser.close()

        if self.pw:
            self.pw.stop()

        self.page = None
        self.context = None
        self.browser = None
        self.pw = None

        return {"ok": True}

    def browser_resize(self, width, height):
        """
        Resize the page's viewport.

        Args:
            width: Viewport width in pixels.
            height: Viewport height in pixels.

        Returns:
            {"ok": True, "width", "height"}

        Raises:
            RuntimeError: If the browser has not been started.
        """
        self._page().set_viewport_size({
            "width": width,
            "height": height
        })

        return {
            "ok": True,
            "width": width,
            "height": height
        }

    # ----------------------------------------------------
    # Navigation
    # ----------------------------------------------------

    def browser_navigate(
        self,
        url,
        wait_until="domcontentloaded"
    ):
        """
        Open a URL in the current page.

        Args:
            url: The full address, such as a file:// or https:// URL.
            wait_until: When to treat navigation as done: commit, domcontentloaded, load or networkidle.

        Returns:
            A dictionary with the final url, the page title and the HTTP status (None if the browser gives no response).

        Raises:
            RuntimeError: If the browser has not been started.
            playwright.sync_api.TimeoutError: If the page does not reach wait_until within the timeout.
            playwright.sync_api.Error: If the address cannot be opened.
        """
        response = self._page().goto(
            url,
            wait_until=wait_until,
            timeout=self.timeout
        )

        return {
            "url": self.page.url,
            "title": self.page.title(),
            "status": response.status if response else None
        }

    def browser_navigate_back(self):
        """
        Go back one page in the browser history.

        Returns:
            A dictionary with the current url and the HTTP status of the page.

        Raises:
            RuntimeError: If the browser has not been started.
            playwright.sync_api.TimeoutError: If the previous page does not load within the timeout.
        """
        response = self._page().go_back(
            wait_until="domcontentloaded"
        )

        return {
            "url": self.page.url,
            "status": response.status if response else None
        }

    # ----------------------------------------------------
    # Find / click / interact
    # ----------------------------------------------------

    def browser_find(self, target, by="text"):
        """
        Check whether an element exists on the page.

        Args:
            target: The locator value.
            by: The strategy: css, text, label, placeholder, testid or role.

        Returns:
            A dictionary with found, the match count, and the first match's text (None when there is none).

        Raises:
            RuntimeError: If the browser has not been started.
            ValueError: If by is "role" and target has no "role:name" colon.
        """
        locator = self._locator(target, by)

        count = locator.count()

        return {
            "found": count > 0,
            "count": count,
            "text": locator.first.inner_text()
            if count else None
        }

    def browser_click(self, target, by="css"):
        """
        Click the first element that matches.

        Args:
            target: The locator value.
            by: The strategy: css, text, label, placeholder, testid or role.

        Returns:
            {"ok": True}

        Raises:
            RuntimeError: If the browser has not been started.
            playwright.sync_api.TimeoutError: If nothing matches, or the element never becomes visible and enabled, within the timeout.
        """
        self._locator(target, by).first.click()

        return {"ok": True}

    def browser_hover(self, target, by="css"):
        """
        Move the mouse over the first element that matches.

        Args:
            target: The locator value.
            by: The strategy: css, text, label, placeholder, testid or role.

        Returns:
            {"ok": True}

        Raises:
            RuntimeError: If the browser has not been started.
            playwright.sync_api.TimeoutError: If nothing matches within the timeout.
        """
        self._locator(target, by).first.hover()

        return {"ok": True}

    def browser_type(
        self,
        target,
        text,
        by="css",
        delay=0
    ):
        """
        Type text into an element one key at a time.

        Args:
            target: The locator value.
            text: The text to type.
            by: The strategy: css, text, label, placeholder, testid or role.
            delay: Milliseconds between key presses.

        Returns:
            {"ok": True}

        Raises:
            RuntimeError: If the browser has not been started.
            playwright.sync_api.TimeoutError: If the element is not found within the timeout.
        """
        locator = self._locator(target, by)

        locator.press_sequentially(
            text,
            delay=delay
        )

        return {"ok": True}

    def browser_press_key(
        self,
        key,
        target=None,
        by="css"
    ):
        """
        Press a keyboard key on one element, or on the page when no target is given.

        Args:
            key: A Playwright key name such as Enter, Escape, Tab, ArrowDown or Control+A.
            target: The locator value of the element to press it on; None for the page.
            by: The strategy for target.

        Returns:
            {"ok": True}

        Raises:
            RuntimeError: If the browser has not been started.
            playwright.sync_api.TimeoutError: If the target is not found within the timeout.
        """
        if target:
            self._locator(target, by).press(key)
        else:
            self._page().keyboard.press(key)

        return {"ok": True}

    def browser_select_option(
        self,
        target,
        value,
        by="css"
    ):
        """
        Choose an option in a select (dropdown) element.

        Args:
            target: The locator value of the select element.
            value: The option's value attribute.
            by: The strategy for target.

        Returns:
            The list of values now selected.

        Raises:
            RuntimeError: If the browser has not been started.
            playwright.sync_api.TimeoutError: If the element or option is not found within the timeout.
        """
        result = self._locator(
            target,
            by
        ).select_option(value=value)

        return result

    # ----------------------------------------------------
    # Forms
    # ----------------------------------------------------

    def browser_fill_form(self, fields):
        """
        Fill several form fields in one call.

        Args:
            fields: A list of dictionaries with "target", "value", an optional "by" (default "css") and an optional
                "type": "text" (default), "select" or "check".

        Returns:
            A list of {"target", "ok"} results, one per field.

        Raises:
            KeyError: If a field has no "target".
            RuntimeError: If the browser has not been started.
            playwright.sync_api.TimeoutError: If a field is not found within the timeout.

        Example:

        fields = [
            {
                "target": "#username",
                "value": "abc",
                "by": "css"
            },
            {
                "target": "Password",
                "value": "secret",
                "by": "label"
            }
        ]
        """

        results = []

        for field in fields:

            target = field["target"]
            value = field.get("value", "")
            by = field.get("by", "css")

            locator = self._locator(target, by)

            field_type = field.get("type", "text")

            if field_type == "select":
                locator.select_option(value=value)

            elif field_type == "check":
                if value:
                    locator.check()
                else:
                    locator.uncheck()

            else:
                locator.fill(str(value))

            results.append({
                "target": target,
                "ok": True
            })

        return results

    # ----------------------------------------------------
    # Drag / drop
    # ----------------------------------------------------

    def browser_drag(
        self,
        source,
        target,
        source_by="css",
        target_by="css"
    ):
        """
        Drag one element onto another.

        Args:
            source: The locator value of the element to drag.
            target: The locator value of the element to drop it on.
            source_by: The strategy for source.
            target_by: The strategy for target.

        Returns:
            {"ok": True}

        Raises:
            RuntimeError: If the browser has not been started.
            playwright.sync_api.TimeoutError: If either element is not found within the timeout.
        """
        self._locator(
            source,
            source_by
        ).drag_to(
            self._locator(
                target,
                target_by
            )
        )

        return {"ok": True}

    def browser_drop(
        self,
        source,
        target,
        source_by="css",
        target_by="css"
    ):
        """
        Drag one element and drop it on another; the same as browser_drag.

        Args:
            source: The locator value of the element to drag.
            target: The locator value of the element to drop it on.
            source_by: The strategy for source.
            target_by: The strategy for target.

        Returns:
            {"ok": True}

        Raises:
            RuntimeError: If the browser has not been started.
            playwright.sync_api.TimeoutError: If either element is not found within the timeout.
        """
        return self.browser_drag(
            source,
            target,
            source_by,
            target_by
        )

    # ----------------------------------------------------
    # Files
    # ----------------------------------------------------

    def browser_file_upload(
        self,
        target,
        files,
        by="css"
    ):
        """
        Attach local files to a file input.

        Args:
            target: The locator value of the file input.
            files: A path, or a list of paths, of the files to upload.
            by: The strategy for target.

        Returns:
            {"ok": True}

        Raises:
            RuntimeError: If the browser has not been started.
            playwright.sync_api.Error: If a file does not exist or the element is not a file input.
        """
        self._locator(
            target,
            by
        ).set_input_files(files)

        return {"ok": True}

    # ----------------------------------------------------
    # JavaScript
    # ----------------------------------------------------

    def browser_evaluate(
        self,
        javascript,
        argument=None
    ):
        """
        Run JavaScript in the page and return its result.

        Args:
            javascript: A JavaScript expression or function, such as "() => document.title".
            argument: An optional JSON-serialisable value passed to the function.

        Returns:
            The JSON-serialisable result.

        Raises:
            RuntimeError: If the browser has not been started.
            playwright.sync_api.Error: If the JavaScript throws or the result cannot be serialised.
        """
        if argument is None:
            return self._page().evaluate(
                javascript
            )

        return self._page().evaluate(
            javascript,
            argument
        )

    def browser_run_code_unsafe(
        self,
        javascript
    ):
        """
        Run arbitrary JavaScript in the page; the same as browser_evaluate without an argument. Never run code taken
        from an untrusted page.

        Args:
            javascript: The JavaScript to run.

        Returns:
            The JSON-serialisable result.

        Raises:
            RuntimeError: If the browser has not been started.
            playwright.sync_api.Error: If the JavaScript throws or the result cannot be serialised.
        """
        return self.browser_evaluate(
            javascript
        )

    # ----------------------------------------------------
    # Screenshot / page snapshot
    # ----------------------------------------------------

    def browser_take_screenshot(
        self,
        path="screenshot.png",
        full_page=True
    ):
        """
        Save a screenshot of the current page.

        Args:
            path: Where to save the image, relative to the working folder unless absolute.
            full_page: True to capture the whole scrollable page rather than the visible part.

        Returns:
            The path the screenshot was saved to.

        Raises:
            RuntimeError: If the browser has not been started.
            playwright.sync_api.Error: If the file cannot be written.
        """
        self._page().screenshot(
            path=path,
            full_page=full_page
        )

        return path

    def browser_snapshot(
        self,
        max_chars=25000
    ):
        """
        Compact snapshot for an LLM agent.

        Much better than returning the full HTML DOM.

        Args:
            max_chars: Maximum amount of visible page text to return before it is cut with "...[truncated]".

        Returns:
            A dictionary with the page url, title, visible text, and up to 400 headings, links, buttons and inputs
            (each with its index, tag, text, href, id, name and placeholder).

        Raises:
            RuntimeError: If the browser has not been started.
            playwright.sync_api.Error: If the page cannot be read, for example while it is navigating.
        """

        result = self._page().evaluate("""
        () => {

            const clean = text =>
                (text || "")
                .replace(/\\s+/g, " ")
                .trim();

            const elements = [
                ...document.querySelectorAll(
                    "h1,h2,h3,a,button,input,textarea,select"
                )
            ];

            return {
                url: location.href,

                title: document.title,

                text: clean(
                    document.body?.innerText || ""
                ),

                elements: elements
                    .slice(0, 400)
                    .map((el, index) => ({
                        index: index,
                        tag: el.tagName.toLowerCase(),
                        text: clean(
                            el.innerText ||
                            el.value ||
                            el.getAttribute("aria-label")
                        ),
                        href: el.href || null,
                        id: el.id || null,
                        name: el.getAttribute("name"),
                        placeholder:
                            el.getAttribute("placeholder")
                    }))
            };
        }
        """)

        if len(result["text"]) > max_chars:
            result["text"] = (
                result["text"][:max_chars]
                + "...[truncated]"
            )

        return result

    # ----------------------------------------------------
    # Console
    # ----------------------------------------------------

    def browser_console_messages(
        self,
        clear=False
    ):
        """
        The console messages and uncaught page errors captured so far.

        Args:
            clear: True to forget the stored messages after returning them.

        Returns:
            A list of {"type", "text"} dictionaries; type is a console level such as "error", or "pageerror".
        """
        result = list(self.console_logs)

        if clear:
            self.console_logs.clear()

        return result

    # ----------------------------------------------------
    # Network
    # ----------------------------------------------------

    def browser_network_requests(
        self,
        contains=None,
        clear=False
    ):
        """
        The network requests the page has made so far.

        Args:
            contains: Only return requests whose URL contains this text, ignoring case.
            clear: True to forget all stored requests after returning them.

        Returns:
            A list of {"url", "method", "resource_type"} dictionaries.
        """
        result = self.requests

        if contains:
            result = [
                r for r in result
                if contains.lower()
                in r["url"].lower()
            ]

        result = list(result)

        if clear:
            self.requests.clear()

        return result

    def browser_network_request(
        self,
        url_contains
    ):
        """
        Find the most recent network request whose URL contains some text.

        Args:
            url_contains: Text to look for in the URL, ignoring case.

        Returns:
            The matching {"url", "method", "resource_type"} dictionary, or None if there is none.
        """
        for request in reversed(
            self.requests
        ):
            if (
                url_contains.lower()
                in request["url"].lower()
            ):
                return request

        return None

    # ----------------------------------------------------
    # Dialog
    # ----------------------------------------------------

    def browser_handle_dialog(
        self,
        accept=True,
        prompt_text=""
    ):
        """
        Accept or dismiss the alert, confirm or prompt dialog the page is waiting on.

        Args:
            accept: True to accept the dialog, False to dismiss it.
            prompt_text: The text to enter when the dialog is a prompt.

        Returns:
            {"ok": True, "message"} with the dialog's text, or {"ok": False, "reason": "No dialog"} when none is open.

        Raises:
            playwright.sync_api.Error: If the dialog was already closed by the page.
        """
        if not self.dialog:
            return {
                "ok": False,
                "reason": "No dialog"
            }

        message = self.dialog.message

        if accept:
            self.dialog.accept(
                prompt_text
            )
        else:
            self.dialog.dismiss()

        self.dialog = None

        return {
            "ok": True,
            "message": message
        }

    # ----------------------------------------------------
    # Tabs
    # ----------------------------------------------------

    def browser_tabs(
        self,
        action="list",
        index=None,
        url=None
    ):
        """
        List, open, switch between or close browser tabs.

        Args:
            action: "list", "new", "switch" or "close".
            index: The tab number for switch or close; close defaults to the current tab.
            url: An address to open in the new tab.

        Returns:
            For list, a list of {"index", "url", "title"}; for new, the new tab's index and url; otherwise {"ok": True}.

        Raises:
            ValueError: If action is not list, new, switch or close.
            IndexError: If index does not match an open tab.
            AttributeError: If the browser has not been started.
        """
        pages = self.context.pages

        if action == "list":

            return [
                {
                    "index": i,
                    "url": page.url,
                    "title": page.title()
                }
                for i, page
                in enumerate(pages)
            ]

        if action == "new":

            page = self.context.new_page()

            if url:
                page.goto(
                    url,
                    wait_until="domcontentloaded"
                )

            self.page = page

            return {
                "index":
                    len(self.context.pages) - 1,
                "url": page.url
            }

        if action == "switch":

            self.page = pages[index]

            self.page.bring_to_front()

            return {
                "ok": True,
                "url": self.page.url
            }

        if action == "close":

            if index is None:
                index = pages.index(
                    self.page
                )

            pages[index].close()

            remaining = self.context.pages

            if remaining:
                self.page = remaining[-1]
            else:
                self.page = (
                    self.context.new_page()
                )

            return {"ok": True}

        raise ValueError(
            "action must be list/new/switch/close"
        )

    # ----------------------------------------------------
    # Waiting
    # ----------------------------------------------------

    def browser_wait_for(
        self,
        target=None,
        by="css",
        state="visible",
        seconds=None
    ):
        """
        Wait for an element to reach a state, or just wait a fixed time.

        Args:
            target: The locator value to wait for. Required unless seconds is given.
            by: The strategy for target.
            state: attached, detached, visible or hidden.
            seconds: If given, wait this long and ignore target.

        Returns:
            {"ok": True}, with "seconds" added when a fixed time was waited.

        Raises:
            RuntimeError: If the browser has not been started.
            playwright.sync_api.TimeoutError: If the element does not reach the state within the timeout.
        """
        if seconds is not None:

            time.sleep(seconds)

            return {
                "ok": True,
                "seconds": seconds
            }

        self._locator(
            target,
            by
        ).first.wait_for(
            state=state,
            timeout=self.timeout
        )

        return {"ok": True}

    # ----------------------------------------------------
    # Extra useful tools for agents
    # ----------------------------------------------------

    def get_text(
        self,
        target,
        by="css",
        all_matches=False
    ):
        """
        Read the visible text of one element, or of every match.

        Args:
            target: The locator value.
            by: The strategy: css, text, label, placeholder, testid or role.
            all_matches: True to return the text of every match instead of only the first.

        Returns:
            The first match's text, or a list of every match's text when all_matches is True.

        Raises:
            RuntimeError: If the browser has not been started.
            playwright.sync_api.TimeoutError: If nothing matches within the timeout.
        """
        locator = self._locator(
            target,
            by
        )

        if all_matches:
            return locator.all_inner_texts()

        return locator.first.inner_text()

    def extract_links(
        self,
        limit=100
    ):
        """
        List the links on the current page.

        Args:
            limit: Maximum number of links to return.

        Returns:
            A list of {"text", "href"} dictionaries.

        Raises:
            RuntimeError: If the browser has not been started.
        """
        return self._page().locator(
            "a"
        ).evaluate_all(
            """
            (elements, limit) =>
                elements
                .slice(0, limit)
                .map(a => ({
                    text:
                        (a.innerText || "")
                        .trim(),
                    href:
                        a.href || null
                }))
            """,
            limit
        )

    def extract_headlines(
        self,
        limit=5
    ):
        """
        Fast news extraction.

        Doesn't open each article.

        Args:
            limit: Maximum number of headlines to return.

        Returns:
            A list of {"title", "url"} dictionaries; short or duplicate titles are skipped.

        Raises:
            RuntimeError: If the browser has not been started.
        """

        return self._page().evaluate(
            """
            (limit) => {

                const selectors = [
                    "article h1 a",
                    "article h2 a",
                    "article h3 a",
                    "main h1 a",
                    "main h2 a",
                    "main h3 a",
                    "h1 a",
                    "h2 a",
                    "h3 a"
                ];

                const nodes =
                    document.querySelectorAll(
                        selectors.join(",")
                    );

                const results = [];
                const seen = new Set();

                for (const node of nodes) {

                    const text =
                        (node.innerText || "")
                        .replace(/\\s+/g, " ")
                        .trim();

                    if (text.length < 15)
                        continue;

                    const normalized =
                        text.toLowerCase();

                    if (seen.has(normalized))
                        continue;

                    seen.add(normalized);

                    results.push({
                        title: text,
                        url: node.href || null
                    });

                    if (
                        results.length >= limit
                    )
                        break;
                }

                return results;
            }
            """,
            limit
        )
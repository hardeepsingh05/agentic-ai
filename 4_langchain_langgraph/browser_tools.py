from playwright.sync_api import sync_playwright
import time


class BrowserTools:
    def __init__(self, headless=True, timeout=15000):
        self.headless = headless
        self.timeout = timeout

        self.pw = None
        self.browser = None
        self.context = None
        self.page = None

        self.console_logs = []
        self.requests = []
        self.dialog = None

    def start(self):
        self.pw = sync_playwright().start()

        self.browser = self.pw.chromium.launch(
            headless=self.headless
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
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")
        return self.page

    def _locator(self, target, by="css"):
        page = self._page()

        if by == "css":
            return page.locator(target)

        if by == "text":
            return page.get_by_text(target)

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
        locator = self._locator(target, by)

        count = locator.count()

        return {
            "found": count > 0,
            "count": count,
            "text": locator.first.inner_text()
            if count else None
        }

    def browser_click(self, target, by="css"):
        self._locator(target, by).first.click()

        return {"ok": True}

    def browser_hover(self, target, by="css"):
        self._locator(target, by).first.hover()

        return {"ok": True}

    def browser_type(
        self,
        target,
        text,
        by="css",
        delay=0
    ):
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
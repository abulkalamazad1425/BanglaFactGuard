from __future__ import annotations

import asyncio
import sys
import types


class _Route:
    def __init__(self, page, url: str) -> None:
        self.request = types.SimpleNamespace(
            url=url,
            resource_type="document",
            frame=page.main_frame,
            is_navigation_request=lambda: True,
        )
        self.aborted = False

    async def abort(self):
        self.aborted = True

    async def continue_(self):
        return None


class _Page:
    def __init__(self, scripts: dict, opened: list, handlers: list, hung: list) -> None:
        self.scripts, self.opened, self.handlers, self.hung = scripts, opened, handlers, hung
        self.script: dict = {}
        self.url = None
        self.contents: list = []
        self.main_frame = types.SimpleNamespace(page=self)

    async def _offer(self, url: str) -> bool:
        route = _Route(self, url)
        for handler in self.handlers:
            await handler(route)
        return not route.aborted

    async def goto(self, url, **kw):
        self.opened.append(url)
        self.script = self.scripts[url]
        self.contents = list(self.script.get("contents", [""]))
        if self.script.get("crash"):
            raise RuntimeError("navigation failed")
        if self.script.get("hang"):
            stopped = asyncio.get_running_loop().create_future()
            self.hung.append(stopped)
            await stopped
        final = self.script.get("final")
        if final and self.handlers:
            if self.script.get("late"):
                asyncio.get_running_loop().call_later(0.01, lambda: asyncio.ensure_future(self._offer(final)))
            elif not await self._offer(final):
                raise RuntimeError("net::ERR_ABORTED")
            self.url = url
            return
        self.url = url if self.script.get("late") else self.script.get("final", url)

    async def wait_for_url(self, predicate, timeout):
        if self.script.get("late") and "final" in self.script:
            self.url = self.script["final"]
        if not predicate(self.url):
            raise TimeoutError("still on the interstitial")

    async def wait_for_timeout(self, ms):
        return None

    async def content(self):
        return self.contents.pop(0) if len(self.contents) > 1 else self.contents[0]

    async def close(self):
        return None


def install(monkeypatch, scripts: dict, opened: list | None = None, *, launch_error: Exception | None = None) -> list:
    opened = [] if opened is None else opened

    handlers: list = []
    hung: list = []

    class Context:
        async def route(self, pattern, handler):
            if pattern == "**/*":
                handlers.append(handler)

        async def new_page(self):
            return _Page(scripts, opened, handlers, hung)

        async def close(self):
            return None

    class Browser:
        async def new_context(self, **kw):
            return Context()

        async def close(self):
            return None

    async def launch(**kw):
        if launch_error:
            raise launch_error
        return Browser()

    async def stop():
        for waiting in hung:
            if not waiting.done():
                waiting.set_exception(RuntimeError("Target page, context or browser has been closed"))

    driver = types.SimpleNamespace(chromium=types.SimpleNamespace(launch=launch), stop=stop)

    class Manager:
        async def start(self):
            return driver

        async def __aenter__(self):
            return driver

        async def __aexit__(self, *exc):
            return None

    module = types.ModuleType("playwright.async_api")
    module.async_playwright = Manager
    monkeypatch.setitem(sys.modules, "playwright.async_api", module)
    return opened


def uninstall(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "playwright.async_api", None)

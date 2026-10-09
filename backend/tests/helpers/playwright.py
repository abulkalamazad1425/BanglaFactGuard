"""A scripted stand-in for `playwright.async_api`, so browser-fallback logic
runs without launching Chromium.

`scripts[url]` describes one page:
    contents  successive `page.content()` values (the last one repeats)
    final     the URL the page ends on (a redirect)
    late      the redirect only happens while waiting for it (`wait_for_url`)
    crash     `goto` raises
"""

from __future__ import annotations

import sys
import types


class _Page:
    def __init__(self, scripts: dict, opened: list) -> None:
        self.scripts, self.opened = scripts, opened
        self.script: dict = {}
        self.url = None
        self.contents: list = []

    async def goto(self, url, **kw):
        self.opened.append(url)
        self.script = self.scripts[url]
        self.contents = list(self.script.get("contents", [""]))
        if self.script.get("crash"):
            raise RuntimeError("navigation failed")
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
    """Install the fake module; returns the list of URLs opened in pages."""
    opened = [] if opened is None else opened

    class Context:
        async def route(self, pattern, handler):
            return None

        async def new_page(self):
            return _Page(scripts, opened)

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

    class Manager:
        async def __aenter__(self):
            return types.SimpleNamespace(chromium=types.SimpleNamespace(launch=launch))

        async def __aexit__(self, *exc):
            return None

    module = types.ModuleType("playwright.async_api")
    module.async_playwright = Manager
    monkeypatch.setitem(sys.modules, "playwright.async_api", module)
    return opened


def uninstall(monkeypatch) -> None:
    """Make `from playwright.async_api import ...` raise ImportError."""
    monkeypatch.setitem(sys.modules, "playwright.async_api", None)

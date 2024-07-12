from contextlib import asynccontextmanager
from typing import AsyncGenerator
from urllib.parse import urlparse

from playwright.async_api import async_playwright, Page, ProxySettings
from playwright_stealth import stealth_async

from harambe.handlers import UnnecessaryResourceHandler


def proxy_from_url(url: str) -> ProxySettings:
    parsed = urlparse(url, allow_fragments=False)

    if not parsed.hostname:
        parsed = urlparse(f"http://{url}", allow_fragments=False)

    if not all(
        [
            parsed.hostname,
            parsed.username,
            parsed.password,
        ]
    ):
        raise ValueError(f"Invalid proxy URL: {url}")

    proxy: ProxySettings = {
        "server": parsed.hostname,
        "username": parsed.username,
        "password": parsed.password,
    }

    if parsed.port:
        proxy["server"] += f":{parsed.port}"

    return proxy


@asynccontextmanager
async def playwright_harness(
    headless: bool,
    cdp_endpoint: str | None,
    proxy: str | None = None,
) -> AsyncGenerator[Page, None]:
    """
    Context manager for Playwright. Starts a new browser, context, and page, and closes them when done.
    Also does some basic setup like setting the viewport, user agent, ignoring HTTPS errors, creation of HAR file, and stealth.

    :param headless: launch browser in headless mode
    :param cdp_endpoint: Chrome DevTools Protocol endpoint to connect to (if using a remote browser)
    :param proxy: proxy server to use
    :return: async generator yielding a Playwright page
    """

    async with async_playwright() as p:
        browser = await (
            p.chromium.connect_over_cdp(endpoint_url=cdp_endpoint)
            if cdp_endpoint
            else p.chromium.launch(headless=headless)
        )

        ctx = await browser.new_context(
            viewport={"width": 1280, "height": 1024},
            ignore_https_errors=True,
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            proxy=proxy_from_url(proxy) if proxy else None,
        )

        ctx.set_default_timeout(60000)
        await ctx.route("**/*", UnnecessaryResourceHandler().handle)

        page = await ctx.new_page()
        await stealth_async(page)

        try:
            yield page
        finally:
            await ctx.close()
            await browser.close()

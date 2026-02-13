from typing import Optional


def fetch_page_with_playwright(
    url: str,
    user_agent: str,
    timeout_seconds: int,
    wait_selector: Optional[str] = None,
) -> str:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is not installed. Run: pip install playwright; python -m playwright install chromium"
        ) from exc

    timeout_ms = max(1000, int(timeout_seconds) * 1000)

    with sync_playwright() as playwright:
        browser = None
        launch_errors = []
        try:
            browser = playwright.chromium.launch(headless=True)
        except Exception as exc:
            launch_errors.append(str(exc))

        if browser is None:
            try:
                browser = playwright.chromium.launch(channel="msedge", headless=True)
            except Exception as exc:
                launch_errors.append(str(exc))
                raise RuntimeError(
                    "Playwright browser launch failed. Install browser with: python -m playwright install chromium"
                ) from exc

        context = browser.new_context(user_agent=user_agent)
        page = context.new_page()
        page.goto(url, wait_until="networkidle", timeout=timeout_ms)
        if wait_selector:
            page.wait_for_selector(wait_selector, timeout=timeout_ms)
        content = page.content()
        context.close()
        browser.close()
        return content

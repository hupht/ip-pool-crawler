import json
from typing import Any, Optional


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


def fetch_page_and_api_payloads_with_playwright(
    url: str,
    user_agent: str,
    timeout_seconds: int,
    wait_selector: Optional[str] = None,
    max_payloads: int = 20,
    max_response_bytes: int = 200000,
) -> tuple[str, list[dict[str, Any]]]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is not installed. Run: pip install playwright; python -m playwright install chromium"
        ) from exc

    timeout_ms = max(1000, int(timeout_seconds) * 1000)
    payload_limit = max(1, int(max_payloads))
    response_size_limit = max(1024, int(max_response_bytes))

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
        captured_payloads: list[dict[str, Any]] = []

        def _on_response(response) -> None:
            if len(captured_payloads) >= payload_limit:
                return

            try:
                resource_type = response.request.resource_type
                if resource_type not in {"xhr", "fetch"}:
                    return

                content_type = str(response.headers.get("content-type", "")).lower()
                if "json" not in content_type:
                    return

                body_text = response.text()
                if not body_text:
                    return
                if len(body_text.encode("utf-8", errors="ignore")) > response_size_limit:
                    return

                payload = json.loads(body_text)
                captured_payloads.append(
                    {
                        "url": response.url,
                        "resource_type": resource_type,
                        "payload": payload,
                    }
                )
            except Exception:
                return

        page.on("response", _on_response)
        page.goto(url, wait_until="networkidle", timeout=timeout_ms)
        if wait_selector:
            page.wait_for_selector(wait_selector, timeout=timeout_ms)
        content = page.content()
        context.close()
        browser.close()
        return content, captured_payloads

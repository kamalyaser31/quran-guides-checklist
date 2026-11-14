"""Manual check of index.html: parsing checklist.md and the score."""

import argparse
import functools
import http.server
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
EXPECTED = {"lesson": (76, 39), "review": (69, 39)}


def serve():
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(ROOT)
    )
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def check(condition, message, failures):
    print(("ok   " if condition else "FAIL ") + message)
    if not condition:
        failures.append(message)


def take_screenshots(browser, url, folder):
    folder.mkdir(parents=True, exist_ok=True)
    for name, width in (("desktop", 1280), ("mobile", 390)):
        page = browser.new_page(viewport={"width": width, "height": 900})
        page.goto(url)
        page.wait_for_selector("input[type=checkbox]")
        page.wait_for_timeout(800)
        page.screenshot(path=str(folder / f"{name}-top.png"))
        boxes = page.locator("li[data-core=true] input[type=checkbox]")
        for i in range(0, boxes.count(), 2):
            boxes.nth(i).check()
        page.locator("#item-P2").focus()
        page.screenshot(path=str(folder / f"{name}-items.png"))
        page.click("#submit-button")
        page.wait_for_timeout(900)
        page.screenshot(path=str(folder / f"{name}-result.png"))
        page.close()


def main():
    parser = argparse.ArgumentParser(description="Check index.html in Chromium.")
    parser.add_argument("--browser", help="path to a Chromium executable")
    parser.add_argument("--url", help="test a published page instead of a local one")
    parser.add_argument(
        "--screenshots", type=Path, help="save desktop and mobile screenshots here"
    )
    args = parser.parse_args()
    failures = []
    server = serve()
    url = args.url or f"http://127.0.0.1:{server.server_port}/index.html"
    try:
        with sync_playwright() as p:
            # An explicit path lets an older installed Chromium stand in when
            # Playwright's own build is missing.
            browser = p.chromium.launch(executable_path=args.browser)
            page = browser.new_page()
            page.goto(url)
            page.wait_for_selector("input[type=checkbox]")
            if args.screenshots:
                take_screenshots(browser, url, args.screenshots)
            for session, (items, core) in EXPECTED.items():
                # The radios are visually hidden; users click their labels.
                page.click(f"label:has(input[value={session}])")
                boxes = page.locator("input[type=checkbox]")
                check(boxes.count() == items, f"{session}: {items} items", failures)
                core_boxes = page.locator("li[data-core=true] input[type=checkbox]")
                check(core_boxes.count() == core, f"{session}: {core} core", failures)
                for i in range(core_boxes.count()):
                    core_boxes.nth(i).check()
                core_boxes.nth(0).uncheck()
                page.click("#submit-button")
                heading = page.locator("#result-heading").inner_text()
                check("97" in heading, f"{session}: 38/39 -> 97% ({heading})", failures)
                missed = page.locator("section[aria-labelledby=result-heading] li")
                check(
                    missed.filter(has_text="1.").count() >= 1,
                    f"{session}: missed item listed",
                    failures,
                )
                focused = page.evaluate("document.activeElement.tagName")
                check(
                    focused == "SECTION", f"{session}: focus moves to result", failures
                )
                page.check("#item-P1")
                check(
                    not page.locator("#result-heading").is_visible(),
                    f"{session}: result hides after a change",
                    failures,
                )
                page.once("dialog", lambda dialog: dialog.accept())
                page.click("text=تقييم جديد")
                check(
                    page.locator("input[type=checkbox]:checked").count() == 0,
                    f"{session}: reset clears checks",
                    failures,
                )
            browser.close()
    finally:
        server.shutdown()
    print(f"{len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

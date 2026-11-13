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


def main():
    parser = argparse.ArgumentParser(description="Check index.html in Chromium.")
    parser.add_argument("--browser", help="path to a Chromium executable")
    args = parser.parse_args()
    failures = []
    server = serve()
    url = f"http://127.0.0.1:{server.server_port}/index.html"
    try:
        with sync_playwright() as p:
            # An explicit path lets an older installed Chromium stand in when
            # Playwright's own build is missing.
            browser = p.chromium.launch(executable_path=args.browser)
            page = browser.new_page()
            page.goto(url)
            page.wait_for_selector("input[type=checkbox]")
            for session, (items, core) in EXPECTED.items():
                page.check(f"input[name=session-type][value={session}]")
                boxes = page.locator("input[type=checkbox]")
                check(boxes.count() == items, f"{session}: {items} items", failures)
                core_boxes = page.locator(
                    "li:has(span:text-is('(أساسي)')) input[type=checkbox]"
                )
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

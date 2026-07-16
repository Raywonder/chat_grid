#!/usr/bin/env python3
"""Static accessibility contract for the public Chat Grid shell.

This intentionally does not replace a real screen-reader/browser pass. It catches
the easy regressions: unnamed controls, expandable controls without state, and
visual-only hiding that can leave stale panels exposed to assistive technology.
"""

from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "client" / "index.html"


class ContractParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.controls: list[dict[str, str]] = []
        self.expanders: list[dict[str, str]] = []
        self.stack: list[dict[str, object]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        if tag in {"button", "a", "input", "select", "textarea"}:
            self.controls.append({"tag": tag, **values})
        if tag == "button" and "aria-expanded" in values:
            self.expanders.append(values)
        self.stack.append({"tag": tag, "attrs": values, "text": []})

    def handle_data(self, data: str) -> None:
        if self.stack:
            self.stack[-1]["text"].append(data)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index]["tag"] == tag:
                self.stack.pop(index)
                return


def main() -> int:
    parser = ContractParser()
    parser.feed(HTML.read_text(encoding="utf-8"))
    failures: list[str] = []
    for control in parser.controls:
        if control["tag"] == "input" and control.get("type") == "hidden":
            continue
        if control["tag"] == "input" and control.get("type") in {"checkbox", "radio"}:
            if not control.get("id"):
                failures.append("checkbox/radio control is missing an id for its label")
        elif control["tag"] in {"button", "select", "textarea"} and not (
            control.get("id") or control.get("aria-label") or control.get("aria-labelledby")
        ):
            failures.append(f"{control['tag']} lacks a stable id or accessible name")
    for expander in parser.expanders:
        if expander.get("aria-expanded") not in {"true", "false"}:
            failures.append(f"expander {expander.get('id', '<unknown>')} has invalid aria-expanded")
        if not expander.get("aria-controls"):
            failures.append(f"expander {expander.get('id', '<unknown>')} lacks aria-controls")
    text = HTML.read_text(encoding="utf-8")
    for panel_id in ("settingsModal", "gridDashboard", "interactiveItemPanel"):
        if f'id="{panel_id}"' in text and f'id="{panel_id}" class="' in text:
            line = next(line for line in text.splitlines() if f'id="{panel_id}"' in line)
            if "hidden" not in line:
                failures.append(f"initially hidden panel {panel_id} lacks the hidden attribute")
    if failures:
        raise SystemExit("accessibility contract failed:\n- " + "\n- ".join(failures))
    print(f"accessibility contract passed ({len(parser.controls)} controls, {len(parser.expanders)} expanders)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

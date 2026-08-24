#!/usr/bin/env python3
"""Small no-Qt guardrail for the isolated native foundation."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src"


def main() -> int:
    files = sorted(SOURCE.rglob("*.h")) + sorted(SOURCE.rglob("*.cpp"))
    if not files:
        raise SystemExit("no Qt foundation sources found")

    combined = "\n".join(path.read_text(encoding="utf-8") for path in files)
    forbidden = ("QWebEngine", "QWebView", "WebView", "<browser", "client/dist")
    failures = [token for token in forbidden if token in combined]
    if failures:
        raise SystemExit("browser dependency found in native foundation: " + ", ".join(failures))
    if "QAccessible" not in combined:
        raise SystemExit("native foundation is missing the cross-screen-reader accessibility path")

    required = {
        "app/main_window.h": ("QMainWindow", "showSettings", "showAbout"),
        "accessibility/accessibility_announcer.h": ("AccessibilityAnnouncer", "announce"),
        "transport/protocol_client.h": ("AuthLogin", "WelcomeReady", "ConnectionState", "QWebSocket", "sendMove"),
        "world/world_viewport.h": ("WorldViewport", "applySnapshot", "moveRequested", "keyPressEvent"),
    }
    for relative, needles in required.items():
        text = (SOURCE / relative).read_text(encoding="utf-8")
        missing = [needle for needle in needles if needle not in text]
        if missing:
            raise SystemExit(f"{relative} is missing: {', '.join(missing)}")

    cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
    for needle in ("Qt6", "Widgets", "Network", "WebSockets", "INDIGINOUS_QT6_BUILD_APP", "source_contract.py"):
        if needle not in cmake:
            raise SystemExit(f"CMakeLists.txt is missing {needle}")
    main_window = (SOURCE / "app/main_window.cpp").read_text(encoding="utf-8")
    if "Focus world viewport" in main_window or "focusWorldAction" in main_window:
        raise SystemExit("the world focus workaround must not be a visible navigation action")

    print(f"source contract passed ({len(files)} C++ files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

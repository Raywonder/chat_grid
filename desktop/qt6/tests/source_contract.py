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

    required = {
        "app/main_window.h": ("QMainWindow", "showSettings", "showAbout"),
        "world/world_viewport.h": ("WorldViewport", "applySnapshot"),
        "transport/protocol_client.h": ("AuthLogin", "WelcomeReady", "ConnectionState"),
    }
    for relative, needles in required.items():
        text = (SOURCE / relative).read_text(encoding="utf-8")
        missing = [needle for needle in needles if needle not in text]
        if missing:
            raise SystemExit(f"{relative} is missing: {', '.join(missing)}")

    cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
    for needle in ("Qt6", "Widgets", "CHATGRID_QT6_BUILD_APP", "source_contract.py"):
        if needle not in cmake:
            raise SystemExit(f"CMakeLists.txt is missing {needle}")

    print(f"source contract passed ({len(files)} C++ files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

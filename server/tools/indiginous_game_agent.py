#!/usr/bin/env python3
"""Ask the local Ollama game companion for a safe structured decision."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

try:
    from app.game_agent_service import OllamaGameAgent
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.game_agent_service import OllamaGameAgent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("context", type=Path, help="JSON file containing current world/game state")
    parser.add_argument("--model", default=None)
    args = parser.parse_args()
    context = json.loads(args.context.read_text(encoding="utf-8"))
    decision = OllamaGameAgent(model=args.model).decide(context)
    print(json.dumps({
        "say": decision.say,
        "actions": list(decision.actions),
        "confidence": decision.confidence,
        "needs_input": decision.needs_input,
        "model": decision.model,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

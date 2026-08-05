#!/usr/bin/env python3
"""Compatibility wrapper for the Indiginous companion presence CLI."""

from __future__ import annotations

import runpy
from pathlib import Path


LEGACY_SCRIPT = Path(__file__).with_name("indiginous_presence_impl.py")


if __name__ == "__main__":
    runpy.run_path(str(LEGACY_SCRIPT), run_name="__main__")

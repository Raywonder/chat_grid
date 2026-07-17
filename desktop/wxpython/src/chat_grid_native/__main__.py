"""Module and packaged-executable entry point."""

# PyInstaller executes this file as the top-level bootstrap, where relative
# imports may not have package context.  Use the installed package name so the
# frozen Windows executable starts reliably instead of exiting immediately.
from chat_grid_native.app import main

raise SystemExit(main())

"""Regression check for generated PowerShell parameters without launching an installer."""
import importlib.util
import pathlib
import re
import sys
import tempfile
from unittest.mock import patch

for number, source in enumerate(sys.argv[1:]):
    spec = importlib.util.spec_from_file_location(f"updater_candidate_{number}", source)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory() as directory:
        root = pathlib.Path(directory)
        (root / "updates").mkdir()
        manifest = module.UpdateManifest("0.4.23", "https://example.test/setup", "a" * 64, "Indiginous_Setup.exe")
        with patch.object(module.sys, "platform", "win32"), patch.object(module.subprocess, "Popen") as launch:
            module.UpdateService("https://example.test/feed", "0.4.22", root).install_after_exit(root / "updates" / manifest.file_name, manifest)
        helper = (root / "updates" / "install-update.ps1").read_text(encoding="utf-8-sig")
        assert not re.search(r"\$pid\b", helper, re.IGNORECASE)
        assert "param([int]$TargetProcessId" in helper
        assert "Wait-Process -Id $TargetProcessId" in helper
        assert "-TargetProcessId" in launch.call_args.args[0]
        assert "-Pid" not in launch.call_args.args[0]
        print(f"PASS: {pathlib.Path(source).name}: generated helper and handoff use nonreserved process parameter")

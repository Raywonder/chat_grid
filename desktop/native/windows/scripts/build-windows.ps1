$ErrorActionPreference = "Stop"
$ScriptRoot = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
$PlatformRoot = Split-Path -Parent $ScriptRoot
$Root = Split-Path -Parent $PlatformRoot
Push-Location $Root
try {
$Venv = Join-Path $Root ".venv"
$Python = Join-Path $Venv "Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Candidates = @("3.13", "3.12", "3.11")
    $Created = $false
    foreach ($Version in $Candidates) {
        & py "-$Version" -c "import sys; raise SystemExit(0 if sys.maxsize > 2**32 else 1)" 2>$null
        if ($LASTEXITCODE -eq 0) {
            & py "-$Version" -m venv $Venv
            if ($LASTEXITCODE -eq 0 -and (Test-Path $Python)) {
                $Created = $true
                break
            }
        }
    }
    if (-not $Created) { throw "Python 3.11-3.13 x64 is required to build Indiginous." }
}
& $Python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed." }
& $Python -m pip install -e "$Root[build,test]"
if ($LASTEXITCODE -ne 0) { throw "Indiginous build dependencies failed to install." }
& $Python -m pytest (Join-Path $Root "tests")
if ($LASTEXITCODE -ne 0) { throw "Indiginous native tests failed." }
$Assets = Join-Path $Root "..\..\client\dist"
if (-not (Test-Path $Assets)) {
    $Assets = Join-Path $Root "assets\web"
}
$Args = @(
    "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
    "--name", "Indiginous", "--collect-all", "wx", "--hidden-import", "wx.html2",
    "--distpath", (Join-Path $PlatformRoot "dist"), "--workpath", (Join-Path $PlatformRoot "build"),
    "--specpath", $PlatformRoot
)
if (Test-Path $Assets) {
    $Args += @("--add-data", "$Assets;assets\web")
}
$NvdaDll = Join-Path $PlatformRoot "vendor\nvda-controller\x64\nvdaControllerClient.dll"
$NvdaLicense = Join-Path $PlatformRoot "vendor\nvda-controller\license.txt"
if (-not (Test-Path $NvdaDll)) { throw "Official NVDA Controller Client DLL is missing." }
$Args += @("--add-binary", "$NvdaDll;nvda", "--add-data", "$NvdaLicense;nvda")
$Args += (Join-Path $Root "desktop_entry.py")
& $Python @Args
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (Join-Path $PlatformRoot "installer\ChatGrid.iss")
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed." }
}
finally {
    Pop-Location
}

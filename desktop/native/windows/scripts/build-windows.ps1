$ErrorActionPreference = "Stop"
$PlatformRoot = Split-Path -Parent $PSScriptRoot
$Root = Split-Path -Parent $PlatformRoot
Push-Location $Root
try {
$Venv = Join-Path $Root ".venv"
$Python = Join-Path $Venv "Scripts\python.exe"
if (-not (Test-Path $Python)) {
    py -3.12 -m venv $Venv
}
& $Python -m pip install --upgrade pip
& $Python -m pip install -e "$Root[build,test]"
& $Python -m pytest (Join-Path $Root "tests")
$Assets = Join-Path $Root "..\..\client\dist"
if (-not (Test-Path $Assets)) {
    $Assets = Join-Path $Root "assets\web"
}
$Args = @(
    "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
    "--name", "ChatGrid", "--collect-all", "wx", "--hidden-import", "wx.html2",
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
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (Join-Path $PlatformRoot "installer\ChatGrid.iss")
}
finally {
    Pop-Location
}

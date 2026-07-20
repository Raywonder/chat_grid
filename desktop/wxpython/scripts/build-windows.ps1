$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Push-Location $Root
try {
$Venv = Join-Path $Root ".venv"
$Python = Join-Path $Venv "Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python312 = $null
    $Uv = Get-Command uv -ErrorAction SilentlyContinue
    if ($Uv) {
        $Python312 = (& $Uv.Source python find 3.12 2>$null | Select-Object -First 1)
    }
    if (-not $Python312 -or -not (Test-Path $Python312)) {
        $Python312 = (& py -V:Astral/CPython3.12.12 -c "import sys; print(sys.executable)" 2>$null | Select-Object -First 1)
    }
    if (-not $Python312 -or -not (Test-Path $Python312)) {
        $PythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
        if ($PythonCommand -and (Test-Path $PythonCommand.Source)) {
            $Python312 = $PythonCommand.Source
        }
    }
    if (-not $Python312 -or -not (Test-Path $Python312)) {
        throw "Python 3.12 was not found through uv or the Python launcher."
    }
    & $Python312 -m venv $Venv
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $Python)) {
        throw "Python 3.12 failed to create the build environment."
    }
}
& $Python -m pip install --upgrade pip
& $Python -m pip install -e "$Root[build,test]"
$PytestBase = "C:\BuildCache\EndiginousPytestTemp"
if (Test-Path $PytestBase) {
    Remove-Item -Recurse -Force $PytestBase
}
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $PytestBase) | Out-Null
& $Python -m pytest (Join-Path $Root "tests") --basetemp $PytestBase
if ($LASTEXITCODE -ne 0) {
    throw "Windows client tests failed with exit code $LASTEXITCODE."
}
$Assets = Join-Path $Root "assets\web"
if (-not (Test-Path $Assets)) {
    $Assets = Join-Path $Root "..\windows\web"
}
$Args = @(
    "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
    "--name", "Endiginous", "--collect-all", "wx", "--hidden-import", "wx.html2",
    "--paths", (Join-Path $Root "src"),
    "--distpath", (Join-Path $Root "dist"), "--workpath", (Join-Path $Root "build"),
    "--specpath", $Root
)
$MsvcpCandidates = @(
    (Join-Path $env:WINDIR "System32\msvcp140.dll"),
    (Join-Path $env:WINDIR "System32\Microsoft-Edge-WebView\msvcp140.dll"),
    "C:\Program Files (x86)\Microsoft\EdgeWebView\Application\msvcp140.dll"
)
$Msvcp = $MsvcpCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Msvcp) {
    throw "MSVC runtime msvcp140.dll was not found; refusing to create a client that crashes at startup."
}
$Args += @("--add-binary", "$Msvcp;.")
if (Test-Path $Assets) {
    $Args += @("--add-data", "$Assets;assets\web")
}
$Args += (Join-Path $Root "src\chat_grid_native\__main__.py")
& $Python @Args
$DistRoot = Join-Path $Root "dist\Endiginous"
Copy-Item (Join-Path $Root "..\..\LICENSE") (Join-Path $DistRoot "LICENSE.txt") -Force
Copy-Item (Join-Path $Root "..\..\THIRD_PARTY_NOTICES.md") (Join-Path $DistRoot "THIRD_PARTY_NOTICES.md") -Force
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (Join-Path $Root "installer\ChatGrid.iss")
}
finally {
    Pop-Location
}

#define MyAppName "Endiginous"
#define MyAppVersion "0.4.4"
#define MyAppPublisher "Raywonder / TappedIn"
#define MyAppExeName "Endiginous.exe"

[Setup]
AppId={{8E748C80-7600-4AA2-97CC-834088D47792}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\Endiginous
DefaultGroupName=Endiginous
OutputDir=..\release
OutputBaseFilename=EndiginousSetup-0.4.4
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=yes
UninstallDisplayIcon={app}\{#MyAppExeName}
LicenseFile=..\..\..\LICENSE

[Files]
Source: "..\dist\Endiginous\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\..\..\..\..\scripts\installers\openclaw-join-windows.ps1"; DestDir: "{app}\OpenClaw"; Flags: ignoreversion

[InstallDelete]
Type: files; Name: "{autodesktop}\Endiginous.lnk"
Type: files; Name: "{group}\Endiginous.lnk"

[Icons]
Name: "{group}\Endiginous"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Endiginous"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"
Name: "openclaw"; Description: "Install and configure OpenClaw and join the approved network"; GroupDescription: "OpenClaw device setup:"; Flags: checkedonce

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Endiginous"; Flags: nowait postinstall skipifsilent
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\OpenClaw\openclaw-join-windows.ps1"" -InstallTailscale -OpenDashboardOnSuccess $true"; Description: "Install and configure OpenClaw on this device"; Flags: shellexec postinstall waituntilterminated skipifsilent; Verb: runas; Tasks: openclaw

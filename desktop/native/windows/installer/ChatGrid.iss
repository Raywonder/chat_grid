#define MyAppName "Chat Grid"
#define MyAppVersion "0.3.8"
#define MyAppPublisher "Raywonder / TappedIn"
#define MyAppExeName "ChatGrid.exe"

[Setup]
AppId={{8E748C80-7600-4AA2-97CC-834088D47792}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\Chat Grid
DefaultGroupName=Chat Grid
OutputDir=..\release
OutputBaseFilename=ChatGridSetup-0.3.8
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=yes
UninstallDisplayIcon={app}\{#MyAppExeName}

[Files]
Source: "..\dist\ChatGrid\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Chat Grid"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Chat Grid"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Classes\chatgrid"; ValueType: string; ValueName: ""; ValueData: "URL:Chat Grid Protocol"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\chatgrid"; ValueType: string; ValueName: "URL Protocol"; ValueData: ""
Root: HKCU; Subkey: "Software\Classes\chatgrid\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName},0"
Root: HKCU; Subkey: "Software\Classes\chatgrid\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Chat Grid"; Flags: nowait postinstall skipifsilent

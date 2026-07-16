#define MyAppName "Chat Grid"
#define MyAppVersion "0.4.0"
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
OutputBaseFilename=ChatGridSetup-0.4.0
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
Source: "..\dist\ChatGrid\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Chat Grid"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Chat Grid"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Chat Grid"; Flags: nowait postinstall skipifsilent

#define MyAppName "Endiginous"
#define MyAppVersion "0.4.6"
#define MyAppPublisher "Raywonder / TappedIn"
#define MyAppExeName "Endiginous.exe"

[Setup]
AppId={{8E748C80-7600-4AA2-97CC-834088D47792}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\Endiginous
UsePreviousAppDir=no
DefaultGroupName=Endiginous
OutputDir=..\release
OutputBaseFilename=IndigenousSetup-0.4.6
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=yes
UninstallDisplayIcon={app}\{#MyAppExeName}

[Files]
Source: "..\dist\Endiginous\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; Replace the complete application payload so renamed/removed files from an
; older Endiginous build cannot survive in the current install directory.
Type: filesandordirs; Name: "{app}\*"
Type: files; Name: "{autodesktop}\Endiginous.lnk"
Type: files; Name: "{group}\Endiginous.lnk"
Type: filesandordirs; Name: "{localappdata}\Programs\Chat Grid"
Type: filesandordirs; Name: "{localappdata}\Programs\ChatGrid"
Type: files; Name: "{autodesktop}\Chat Grid.lnk"
Type: files; Name: "{autodesktop}\ChatGrid.lnk"
Type: files; Name: "{group}\Chat Grid.lnk"
Type: files; Name: "{group}\ChatGrid.lnk"

[Icons]
Name: "{group}\Endiginous"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Endiginous"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Classes\endiginous"; ValueType: string; ValueName: ""; ValueData: "URL:Endiginous Protocol"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\endiginous"; ValueType: string; ValueName: "URL Protocol"; ValueData: ""
Root: HKCU; Subkey: "Software\Classes\endiginous\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName},0"
Root: HKCU; Subkey: "Software\Classes\endiginous\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCU; Subkey: "Software\Classes\chatgrid"; ValueType: string; ValueName: ""; ValueData: "URL:Endiginous Protocol"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\chatgrid"; ValueType: string; ValueName: "URL Protocol"; ValueData: ""
Root: HKCU; Subkey: "Software\Classes\chatgrid\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName},0"
Root: HKCU; Subkey: "Software\Classes\chatgrid\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Endiginous"; Flags: nowait postinstall skipifsilent

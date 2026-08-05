#define MyAppName "Indiginous"
#define MyAppVersion "0.4.18"
#define MyAppPublisher "Raywonder / TappedIn"
#define MyAppExeName "Indiginous.exe"

[Setup]
AppId={{8E748C80-7600-4AA2-97CC-834088D47792}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
; BlindSoftware is the default vendor root. The directory page remains enabled
; so a user may choose another permitted location when needed.
DefaultDirName={autopf}\BlindSoftware\{#MyAppName}
UsePreviousAppDir=no
DefaultGroupName=Indiginous
OutputDir=..\release
OutputBaseFilename=Indiginous_Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=yes
UninstallDisplayIcon={app}\{#MyAppExeName}
LicenseFile=..\..\..\..\INDIGINOUS_APPLICATION_LICENSE.txt

[Files]
Source: "..\dist\Indiginous\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; Replace the complete application payload so renamed/removed files from an
; older Indiginous or legacy build cannot survive in the current install directory.
Type: filesandordirs; Name: "{app}\*"
Type: filesandordirs; Name: "{autopf}\Indiginous"
Type: filesandordirs; Name: "{autopf}\BlindSoftware\Indiginous"
Type: filesandordirs; Name: "{autopf}\BlindSoftware\Endiginous"
Type: filesandordirs; Name: "{autopf}\BlindSoftware\Indigenous"
Type: filesandordirs; Name: "{autopf}\BlindSoftware\Chat Grid"
Type: filesandordirs; Name: "{autopf}\BlindSoftware\ChatGrid"
Type: filesandordirs; Name: "{localappdata}\Programs\Endiginous"
Type: filesandordirs; Name: "{localappdata}\Programs\Indigenous"
Type: filesandordirs; Name: "{localappdata}\Programs\Chat Grid"
Type: filesandordirs; Name: "{localappdata}\Programs\ChatGrid"
Type: files; Name: "{autodesktop}\Indiginous.lnk"
Type: files; Name: "{group}\Indiginous.lnk"
Type: files; Name: "{autodesktop}\Endiginous.lnk"
Type: files; Name: "{autodesktop}\Indigenous.lnk"
Type: files; Name: "{group}\Endiginous.lnk"
Type: files; Name: "{group}\Indigenous.lnk"
Type: files; Name: "{autodesktop}\Chat Grid.lnk"
Type: files; Name: "{autodesktop}\ChatGrid.lnk"
Type: files; Name: "{group}\Chat Grid.lnk"
Type: files; Name: "{group}\ChatGrid.lnk"

[Icons]
Name: "{group}\Indiginous"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Indiginous"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Classes\indiginous"; ValueType: string; ValueName: ""; ValueData: "URL:Indiginous Protocol"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\indiginous"; ValueType: string; ValueName: "URL Protocol"; ValueData: ""
Root: HKCU; Subkey: "Software\Classes\indiginous\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName},0"
Root: HKCU; Subkey: "Software\Classes\indiginous\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCU; Subkey: "Software\Classes\indiginous"; ValueType: string; ValueName: ""; ValueData: "URL:Indiginous legacy protocol"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\indiginous"; ValueType: string; ValueName: "URL Protocol"; ValueData: ""
Root: HKCU; Subkey: "Software\Classes\indiginous\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName},0"
Root: HKCU; Subkey: "Software\Classes\indiginous\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCU; Subkey: "Software\Classes\chatgrid"; ValueType: string; ValueName: ""; ValueData: "URL:Indiginous legacy protocol"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\chatgrid"; ValueType: string; ValueName: "URL Protocol"; ValueData: ""
Root: HKCU; Subkey: "Software\Classes\chatgrid\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName},0"
Root: HKCU; Subkey: "Software\Classes\chatgrid\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Indiginous"; Flags: nowait postinstall skipifsilent

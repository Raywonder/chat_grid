#define MyAppName "Endiginous"
#define MyAppVersion "0.4.1"
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
OutputBaseFilename=EndiginousSetup-0.4.1
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
Type: files; Name: "{autodesktop}\Endiginous.lnk"
Type: files; Name: "{group}\Endiginous.lnk"

[Icons]
Name: "{group}\Endiginous"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Endiginous"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Classes\chatgrid"; ValueType: string; ValueName: ""; ValueData: "URL:Endiginous Protocol"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\chatgrid"; ValueType: string; ValueName: "URL Protocol"; ValueData: ""
Root: HKCU; Subkey: "Software\Classes\chatgrid\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName},0"
Root: HKCU; Subkey: "Software\Classes\chatgrid\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Endiginous"; Flags: nowait postinstall skipifsilent

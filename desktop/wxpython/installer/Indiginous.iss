#define MyAppName "Indiginous"
#define MyAppVersion "0.4.18"
#define MyAppPublisher "Raywonder / TappedIn"
#define MyAppExeName "Indiginous.exe"

#define LatestManifestUrl "https://blind.software/downloads/public/7Kp3mN8vQ2xL5rT9cW6yH1/latest-windows.json"

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
LicenseFile=..\..\..\INDIGINOUS_APPLICATION_LICENSE.txt

[Files]
Source: "..\dist\Indiginous\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; Replace the complete application payload so renamed/removed files from an
; Replace any older Indiginous/legacy payload before installing the new build.
Type: filesandordirs; Name: "{app}\*"
Type: filesandordirs; Name: "{autopf}\Indiginous"
Type: filesandordirs; Name: "{autopf}\BlindSoftware\Indiginous"
Type: filesandordirs; Name: "{autopf}\BlindSoftware\Endiginous"
Type: filesandordirs; Name: "{autopf}\BlindSoftware\Indigenous"
Type: filesandordirs; Name: "{autopf}\BlindSoftware\Chat Grid"
Type: filesandordirs; Name: "{autopf}\BlindSoftware\ChatGrid"
Type: filesandordirs; Name: "{autopf}\Endiginous"
Type: filesandordirs; Name: "{autopf}\Indigenous"
Type: filesandordirs; Name: "{autopf}\Chat Grid"
Type: filesandordirs; Name: "{autopf}\ChatGrid"
Type: filesandordirs; Name: "{localappdata}\Programs\Indiginous"
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
Type: files; Name: "{autodesktop}\Indiginous.lnk"
Type: files; Name: "{group}\Indiginous.lnk"
Type: files; Name: "{autodesktop}\Chat Grid.lnk"
Type: files; Name: "{autodesktop}\ChatGrid.lnk"
Type: files; Name: "{group}\Chat Grid.lnk"
Type: files; Name: "{group}\ChatGrid.lnk"

[Icons]
Name: "{group}\Indiginous"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Indiginous"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Indiginous"; Flags: nowait postinstall skipifsilent

[Code]
function URLDownloadToFile(Caller: Integer; URL, FileName: string; Reserved: Integer; StatusCallback: Integer): Integer;
  external 'URLDownloadToFileA@urlmon.dll stdcall';

function JsonString(const Json, Key: string): string;
var
  Marker: string;
  StartPos, EndPos: Integer;
begin
  Result := '';
  Marker := '"' + Key + '"';
  StartPos := Pos(Marker, Json);
  if StartPos = 0 then Exit;
  StartPos := StartPos + Length(Marker);
  while (StartPos <= Length(Json)) and (Json[StartPos] <> ':') do
    StartPos := StartPos + 1;
  if StartPos > Length(Json) then Exit;
  StartPos := StartPos + 1;
  while (StartPos <= Length(Json)) and (Json[StartPos] <> '"') do
    StartPos := StartPos + 1;
  if StartPos > Length(Json) then Exit;
  StartPos := StartPos + 1;
  EndPos := StartPos;
  while (EndPos <= Length(Json)) and (Json[EndPos] <> '"') do
    EndPos := EndPos + 1;
  if EndPos > Length(Json) then Exit;
  Result := Copy(Json, StartPos, EndPos - StartPos);
end;

function VersionComponent(const Value: string; Index: Integer): Integer;
var
  StartPos, EndPos, CurrentIndex: Integer;
begin
  StartPos := 1;
  CurrentIndex := 0;
  while (CurrentIndex < Index) and (StartPos <= Length(Value)) do begin
    EndPos := Pos('.', Copy(Value, StartPos, Length(Value) - StartPos + 1));
    if EndPos = 0 then begin
      StartPos := Length(Value) + 1;
      Break;
    end;
    StartPos := StartPos + EndPos;
    CurrentIndex := CurrentIndex + 1;
  end;
  if StartPos > Length(Value) then
    Result := 0
  else begin
    EndPos := Pos('.', Copy(Value, StartPos, Length(Value) - StartPos + 1));
    if EndPos = 0 then
      EndPos := Length(Value) - StartPos + 2;
    Result := StrToIntDef(Copy(Value, StartPos, EndPos - 1), 0);
  end;
end;

function VersionIsNewer(const Candidate, Current: string): Boolean;
var
  Index, CandidatePart, CurrentPart: Integer;
begin
  Result := False;
  for Index := 0 to 3 do begin
    CandidatePart := VersionComponent(Candidate, Index);
    CurrentPart := VersionComponent(Current, Index);
    if CandidatePart > CurrentPart then begin
      Result := True;
      Exit;
    end;
    if CandidatePart < CurrentPart then Exit;
  end;
end;

function TryLaunchLatestInstaller(): Boolean;
var
  Http: Variant;
  Manifest, LatestVersion, DownloadUrl, Sha256, TempInstaller: string;
  ExitCode: Integer;
begin
  Result := False;
  if Pos('/INDIGINOUS-LATEST', UpperCase(GetCmdTail)) > 0 then Exit;
  try
    Http := CreateOleObject('WinHttp.WinHttpRequest.5.1');
    Http.Open('GET', '{#LatestManifestUrl}', False);
    Http.SetRequestHeader('User-Agent', 'IndiginousSetup/{#MyAppVersion}');
    Http.Send;
    if Http.Status <> 200 then Exit;
    Manifest := Http.ResponseText;
    LatestVersion := JsonString(Manifest, 'version');
    DownloadUrl := JsonString(Manifest, 'url');
    Sha256 := JsonString(Manifest, 'sha256');
    if (LatestVersion = '') or (DownloadUrl = '') or (Sha256 = '') then Exit;
    if not VersionIsNewer(LatestVersion, '{#MyAppVersion}') then Exit;
    Http := CreateOleObject('WinHttp.WinHttpRequest.5.1');
    Http.Open('GET', DownloadUrl, False);
    Http.SetRequestHeader('User-Agent', 'IndiginousSetup/{#MyAppVersion}');
    Http.Send;
    if Http.Status <> 200 then Exit;
    TempInstaller := ExpandConstant('{tmp}\Indiginous_Setup-latest.exe');
    if URLDownloadToFile(0, DownloadUrl, TempInstaller, 0, 0) <> 0 then Exit;
    if CompareText(GetSHA256OfFile(TempInstaller), Sha256) <> 0 then begin
      DeleteFile(TempInstaller);
      Exit;
    end;
    if Exec(TempInstaller, '/INDIGINOUS-LATEST /SP- /NORESTART', '', SW_SHOWNORMAL, ewNoWait, ExitCode) then
      Result := True;
  except
    { Offline or unavailable update checks must never prevent the requested installer from running. }
  end;
end;

function InitializeSetup(): Boolean;
begin
  if TryLaunchLatestInstaller() then
    Result := False
  else
    Result := True;
end;

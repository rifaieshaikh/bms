#define MyAppVersion "1.0.0"
#define MyAppName "VayBooks-BMS"
#define MyAppPublisher "VayBooks"
#define MyAppURL "https://github.com/rifaieshaikh/bms"
#define MyAppExeName "VayBooks-Launcher.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\..\dist
OutputBaseFilename=VayBooks-BMS-Setup-{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UsePreviousAppDir=yes
UninstallDisplayIcon={app}\tools\VayBooks-Launcher.exe
LicenseFile=..\..\assets\LICENSE.rtf

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Types]
Name: "full"; Description: "Full installation"

[Components]
Name: "app"; Description: "VayBooks-BMS Application"; Types: full; Flags: fixed
Name: "mongodb"; Description: "MongoDB Community Server (local)"; Types: full

[Files]
Source: "..\..\dist\staging\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\..\dist\staging\downloads\mongodb.msi"; DestDir: "{tmp}"; Components: mongodb; Flags: deleteafterinstall

[Dirs]
Name: "{commonappdata}\{#MyAppName}\config"; Permissions: users-modify
Name: "{commonappdata}\{#MyAppName}\logs"; Permissions: users-modify
Name: "{commonappdata}\{#MyAppName}\data\uploads"; Permissions: users-modify
Name: "{commonappdata}\{#MyAppName}\data\backups"; Permissions: users-modify
Name: "{commonappdata}\{#MyAppName}\mongodb\data"; Components: mongodb; Permissions: users-modify
Name: "{commonappdata}\{#MyAppName}\migrations"; Permissions: users-modify

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\tools\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\tools\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Run]
Filename: "{app}\tools\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: postinstall nowait skipifsilent

[UninstallRun]
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -File ""{app}\nssm\uninstall_service.ps1"" -InstallDir ""{app}"""; Flags: runhidden

[Code]
#include "wizard_pages.iss"
#include "silent_params.iss"

var
  DataDir: String;
  SelectedMongoMode: String;
  SelectedMongoUri: String;
  SelectedDbName: String;

procedure InitializeWizard;
begin
  DataDir := ExpandConstant('{commonappdata}\{#MyAppName}');
  if not WizardSilent then
  begin
    InitializeMongoWizardPages;
    BindMongoWizardEvents;
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (CurPageID = MongoPage.ID) and (not WizardSilent) then
    Result := MongoPageValidate;
end;

function ShouldInstallMongo: Boolean;
begin
  if WizardSilent then
    Result := (CompareText(GetSilentMongoMode(''), 'local') = 0)
  else
    Result := MongoLocalRadio.Checked;
end;

function GetSelectedMongoMode: String;
begin
  if WizardSilent then
    Result := GetSilentMongoMode('')
  else if MongoLocalRadio.Checked then
    Result := 'local'
  else
    Result := 'remote';
end;

function GetSelectedMongoUri: String;
begin
  if WizardSilent then
  begin
    if CompareText(GetSilentMongoMode(''), 'local') = 0 then
      Result := 'mongodb://localhost:27017'
    else
      Result := GetSilentMongoUri;
  end
  else
    Result := GetMongoUri;
end;

function GetSelectedDbName: String;
begin
  if WizardSilent then
    Result := GetSilentDbName
  else
    Result := GetDbName;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
  Params: String;
begin
  if CurStep = ssInstall then
  begin
    Params := '-ExecutionPolicy Bypass -File "' + ExpandConstant('{app}\scripts\pre_upgrade.ps1') +
      '" -InstallDir "' + ExpandConstant('{app}') + '" -DataDir "' + DataDir +
      '" -AppVersion "{#MyAppVersion}"';
    Exec('powershell.exe', Params, '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;

  if CurStep = ssPostInstall then
  begin
    SelectedMongoMode := GetSelectedMongoMode;
    SelectedMongoUri := GetSelectedMongoUri;
    SelectedDbName := GetSelectedDbName;

    if ShouldInstallMongo then
    begin
      Exec('msiexec.exe', '/i "' + ExpandConstant('{tmp}\mongodb.msi') + '" /qn ADDLOCAL="all" SHOULD_INSTALL_COMPASS="0"',
        '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    end;

    Params := '-ExecutionPolicy Bypass -File "' + ExpandConstant('{app}\scripts\pre_install.ps1') +
      '" -DataDir "' + DataDir + '"';
    Exec('powershell.exe', Params, '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

    Params := '-ExecutionPolicy Bypass -File "' + ExpandConstant('{app}\scripts\post_install.ps1') +
      '" -InstallDir "' + ExpandConstant('{app}') + '" -DataDir "' + DataDir +
      '" -MongoMode "' + SelectedMongoMode + '" -MongoUri "' + SelectedMongoUri +
      '" -DbName "' + SelectedDbName + '" -AppVersion "{#MyAppVersion}"';
    Exec('powershell.exe', Params, '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;
end;

function InitializeUninstall: Boolean;
var
  Response: Integer;
begin
  Response := MsgBox('Remove user data in ' + ExpandConstant('{commonappdata}\{#MyAppName}') + '?',
    mbConfirmation, MB_YESNOCANCEL);
  if Response = IDCANCEL then
    Result := False
  else if Response = IDYES then
  begin
    DelTree(ExpandConstant('{commonappdata}\{#MyAppName}'), True, True, True);
    Result := True;
  end
  else
    Result := True;
end;

[InstallDelete]
Type: filesandordirs; Name: "{app}\python"
Type: filesandordirs; Name: "{app}\app"
Type: filesandordirs; Name: "{app}\tools"
Type: filesandordirs; Name: "{app}\service"

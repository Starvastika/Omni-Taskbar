#include "generated.iss"
[Setup]
AppId={{BC496763-D42A-4E6F-B473-7CE28DABAC83}
AppName=Omni Taskbar
AppVersion={#OmniVersion}
AppPublisher=Starvastika
AppPublisherURL=https://github.com/Starvastika/Omni-Taskbar
AppSupportURL=https://github.com/Starvastika/Omni-Taskbar/issues
AppUpdatesURL=https://github.com/Starvastika/Omni-Taskbar/releases
DefaultDirName={localappdata}\Programs\Omni-Taskbar
DefaultGroupName=Omni Taskbar
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.22000
OutputDir={#OutputFolder}
OutputBaseFilename=Omni-Taskbar-Setup-{#OmniVersion}
#ifdef OmniFixtureBuild
Compression=lzma2/fast
#else
Compression=lzma2
#endif
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName=Omni Taskbar
UninstallDisplayIcon={app}\Omni-Taskbar.exe
SetupLogging=yes
#ifdef OmniSignCommand
SignTool=omnisign
SignedUninstaller=yes
#endif
CloseApplications=no
RestartApplications=no
DisableProgramGroupPage=yes
LicenseFile={#ProjectRoot}\LICENSE
VersionInfoDescription=Omni Taskbar Setup
VersionInfoProductName=Omni Taskbar
VersionInfoVersion={#OmniVersion}
VersionInfoCopyright=Copyright (c) 2026 Starvastika
[Files]
#include "bootstrap-files.iss"
Source: "{#ImageFolder}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[UninstallDelete]
Type: files; Name: "{app}\omni-installed.json"
[Icons]
Name: "{userprograms}\Omni Taskbar"; Filename: "{app}\Omni-Taskbar.exe"; WorkingDir: "{app}"
[Code]
function GetCurrentProcessId: Cardinal;
  external 'GetCurrentProcessId@kernel32.dll stdcall';
var
  ModePage: TInputOptionWizardPage;
  RemoveData: Boolean;
  LaunchPage: TInputOptionWizardPage;
function DataFolder: String;
begin
  Result := ExpandConstant('{param:DATA_DIR|{userappdata}\Omni-Taskbar}');
end;
function Q(Value: String): String;
begin Result := '"' + Value + '"'; end;
function FixtureFlag(Name: String): Boolean;
begin Result := ExpandConstant('{param:' + Name + '|0}') = '1'; end;
procedure ExtractBootstrap;
begin
#include "bootstrap-extract.iss"
end;
function Mode: String;
begin
  Result := ExpandConstant('{param:UPDATEMODE|}');
  if Result <> '' then Exit;
  case ModePage.SelectedValueIndex of
    0: Result := 'automatic';
    2: Result := 'manual';
  else Result := 'check';
  end;
end;
procedure InitializeWizard;
begin
  ModePage := CreateInputOptionPage(wpSelectDir, 'Keep Omni Taskbar updated',
    'Choose how you want updates to work.',
    'You can change this later in ... > Taskbar Updates. Windows will never restart automatically.', True, False);
  ModePage.Add('Automatic updates - verify and stage stable updates for the next taskbar restart.');
  ModePage.Add('Check automatically - tell me when an update is available; I decide when to install.');
  ModePage.Add('Manual only - check only when I ask.');
  ModePage.SelectedValueIndex := 1;
  LaunchPage := CreateInputOptionPage(ModePage.ID, 'Ready to use Omni Taskbar',
    'Start your taskbar after installation?', 'Autostart is registered for your next sign-in.', False, False);
  LaunchPage.Add('Launch Omni Taskbar after installation');
  LaunchPage.Values[0] := True;
end;
function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := (PageID = ModePage.ID) and FileExists(ExpandConstant('{app}\omni-installed.json'));
end;
function PrepareToInstall(var NeedsRestart: Boolean): String;
var Code: Integer; Args: String;
begin
  Result := '';
  ExtractBootstrap;
  Args := Q(ExpandConstant('{tmp}\installer_backend.py')) + ' prepare --root ' +
    Q(ExpandConstant('{app}')) + ' --data ' + Q(DataFolder) + ' --owner ' + IntToStr(GetCurrentProcessId);
  if not Exec(ExpandConstant('{tmp}\python.exe'), Args, ExpandConstant('{tmp}'), SW_HIDE, ewWaitUntilTerminated, Code) or (Code <> 0) then
    Result := 'Omni Taskbar could not prepare this installation. Your existing files and settings were preserved.';
end;
procedure CurStepChanged(CurStep: TSetupStep);
var Code: Integer; Args: String;
begin
  if CurStep <> ssPostInstall then Exit;
  Args := Q(ExpandConstant('{tmp}\installer_backend.py')) + ' finish --root ' +
    Q(ExpandConstant('{app}')) + ' --data ' + Q(DataFolder) + ' --mode ' + Mode +
    ' --owner ' + IntToStr(GetCurrentProcessId);
  if FixtureFlag('NOLAUNCH') or not LaunchPage.Values[0] then Args := Args + ' --no-launch';
  if FixtureFlag('NOSTARTUP') then Args := Args + ' --no-startup';
  if not Exec(ExpandConstant('{tmp}\python.exe'), Args, ExpandConstant('{tmp}'), SW_HIDE, ewWaitUntilTerminated, Code) or (Code <> 0) then
    RaiseException('Omni Taskbar could not complete its health check. A previous installation was restored where available; your user data was preserved.');
end;
function InitializeUninstall: Boolean;
var Form: TSetupForm; Check: TNewCheckBox; OK: TNewButton;
begin
  Result := True; RemoveData := FixtureFlag('REMOVEDATA');
  if UninstallSilent then Exit;
  Form := CreateCustomForm(ScaleX(450), ScaleY(130), False, False);
  try
    Form.Caption := 'Uninstall Omni Taskbar';
    Check := TNewCheckBox.Create(Form); Check.Parent := Form;
    Check.Left := ScaleX(20); Check.Top := ScaleY(24);
    Check.Width := ScaleX(410); Check.Caption := 'Also remove Omni Taskbar settings and user data';
    Check.Checked := False;
    OK := TNewButton.Create(Form); OK.Parent := Form;
    OK.Left := ScaleX(310); OK.Top := ScaleY(80); OK.Width := ScaleX(120);
    OK.Caption := 'Uninstall'; OK.ModalResult := mrOk; OK.Default := True;
    Result := Form.ShowModal = mrOk; RemoveData := Check.Checked;
  finally Form.Free; end;
end;
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var Code: Integer; Args: String;
begin
  if CurUninstallStep <> usUninstall then Exit;
  Args := Q(ExpandConstant('{app}\shell-updater\installer_backend.py')) +
    ' uninstall --root ' + Q(ExpandConstant('{app}'));
  if FixtureFlag('NOSTARTUP') then Args := Args + ' --no-startup';
  if RemoveData then Args := Args + ' --remove-data';
  if not Exec(ExpandConstant('{app}\runtime\python\python.exe'), Args, ExpandConstant('{app}'), SW_HIDE, ewWaitUntilTerminated, Code) or (Code <> 0) then
    RaiseException('Omni Taskbar could not stop safely. User data was not removed.');
end;

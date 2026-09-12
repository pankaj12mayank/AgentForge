; AgentForge - full Windows installer (Inno Setup 6).
;
; This is the deliverable end-users download and run. It installs the
; AgentForge desktop app with Start Menu icons, an optional desktop shortcut,
; and optional auto-start at sign-in. The interface it launches is the same
; app you can install as a PWA from the browser.
;
; Build steps:
;   1) scripts\build_exe.ps1 writes dist\AgentForge.exe
;   2) iscc installer\AgentForge.iss writes dist\installer\AgentForge-Setup.exe
;   (or simply run scripts\build_installer.ps1 which does both)

#define MyAppName "AgentForge"
#define MyAppVersion "3.1.0"
#define MyAppPublisher "AgentForge"
#define MyAppURL "http://127.0.0.1:8765/"
#define MyAppExeName "AgentForge.exe"

[Setup]
AppId={{0A0D8EF4-6C25-4A9B-9D9C-0EE9EA23C51F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
AppCopyright=Copyright (C) 2026 {#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=auto
OutputDir=..\dist\installer
OutputBaseFilename=AgentForge-Setup-{#MyAppVersion}
SetupIconFile=..\pg_ui\static\favicon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.19041
LicenseFile=LICENSE.txt
ShowLanguageDialog=no
CloseApplications=yes
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a {#MyAppName} icon on my desktop"; GroupDescription: "Shortcuts:"
Name: "startup"; Description: "Start {#MyAppName} automatically when I sign in"; GroupDescription: "Startup:"

[Files]
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "LICENSE.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#MyAppName}"; ValueData: """{app}\{#MyAppExeName}"""; Flags: uninsdeletevalue; Tasks: startup

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName} now"; Flags: nowait postinstall skipifsilent
; Inno Setup Script for MeshForge 3D Universal Studio
; Generates MeshForge3D_v2.0_Setup.exe commercial installer for Windows distribution

#define MyAppName "MeshForge 3D Studio"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "MeshForge 3D Universal"
#define MyAppURL "https://github.com/MeshForge3D"
#define MyAppExeName "MeshForge3D.vbs"

[Setup]
AppId={{C4726B1E-F5E2-4217-A583-9B679B0DF95C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\MeshForge3D
DisableProgramGroupPage=yes
OutputDir=..\dist_installer
OutputBaseFilename=MeshForge3D_v2.0_Setup
SetupIconFile=..\MeshForge3D.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\MeshForge3D.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\MeshForge3D.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\app\*"; DestDir: "{app}\app"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\tsr_sdk\*"; DestDir: "{app}\tsr_sdk"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\requirements.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "wscript.exe"; Parameters: """{app}\{#MyAppExeName}"""; IconFilename: "{app}\MeshForge3D.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "wscript.exe"; Parameters: """{app}\{#MyAppExeName}"""; IconFilename: "{app}\MeshForge3D.ico"; Tasks: desktopicon

[Run]
Filename: "wscript.exe"; Parameters: """{app}\{#MyAppExeName}"""; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

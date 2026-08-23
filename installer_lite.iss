; ============================================================================
; MeshForge 3D — LITE Installer Script (v2.1.0)
; ============================================================================
; Small (<650 MB) web-installer that FITS the VirusTotal upload limit.
; AI libraries (torch/diffusers/transformers) are downloaded automatically on
; first application launch (visible progress window).
;
; Build:  python tools/build_lite.py
; ============================================================================

#define MyAppName "MeshForge 3D"
#define MyAppVersion "2.1.0"
#define MyAppPublisher "MeshForge"
#define MyAppURL "https://meshforge3d.dev"
#define MyAppExeName "MeshForge3D.exe"

[Setup]
AppId={{B2C3D4E5-F6A7-8901-BCDE-F12345678901}
AppName={#MyAppName} Lite
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} Lite {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

SetupIconFile=MeshForge3D.ico
WizardImageFile=installer\wizard_side.bmp
WizardSmallImageFile=installer\wizard_top.bmp
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Lite Installer
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
VersionInfoVersion={#MyAppVersion}
VersionInfoCopyright=(c) 2026 MeshForge

DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
LicenseFile=installer\LICENSE.txt
CloseApplications=yes
RestartApplications=no
Compression=lzma2/max
SolidCompression=yes
LZMANumBlockThreads=4
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequiredOverridesAllowed=dialog
MinVersion=10.0.19041
OutputDir=installer_output
OutputBaseFilename=MeshForge3D_Lite_Setup_v{#MyAppVersion}

#ifdef SignToolName
SignTool={#SignToolName}
SignedUninstaller=yes
#endif

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "lite_runtime\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\MeshForge3D.bat"; IconFilename: "{app}\MeshForge3D.ico"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\MeshForge3D.bat"; IconFilename: "{app}\MeshForge3D.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\MeshForge3D.bat"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

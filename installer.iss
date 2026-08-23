; ============================================================================
; MeshForge 3D — Inno Setup Installer Script (v2.1.0, AV-friendly)
; ============================================================================
; Build:  iscc installer.iss          (or: python build_installer.py)
;
; Anti-Virus best practices applied here:
;   * Setup.exe carries version info + icon + EULA page (not a bare stub)
;   * LZMA2 solid compression of an UNPACKED onedir app (no self-extracting
;     packed payload — the classic malware heuristic trigger)
;   * Stable AppId GUID across versions (reputation builds up over time)
;   * Optional Authenticode signing: pass /DSignToolName="MySignTool"
;     after registering the tool in Inno Setup's SignTools section.
; ============================================================================

#define MyAppName "MeshForge 3D"
#define MyAppVersion "2.1.0"
#define MyAppPublisher "MeshForge"
#define MyAppURL "https://meshforge3d.dev"
#define MyAppExeName "MeshForge3D.exe"

[Setup]
AppId={{B2C3D4E5-F6A7-8901-BCDE-F12345678901}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; --- Version metadata embedded into Setup.exe itself -----------------------
SetupIconFile=MeshForge3D.ico
UninstallIconFile=MeshForge3D.ico
WizardImageFile=installer\wizard_side.bmp
WizardSmallImageFile=installer\wizard_top.bmp
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Installer
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
VersionInfoVersion={#MyAppVersion}
VersionInfoCopyright=(c) 2026 MeshForge

; --- Behavior ---------------------------------------------------------------
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
OutputBaseFilename=MeshForge3D_Setup_v{#MyAppVersion}

; --- Optional code signing (removes SmartScreen & most AV warnings) --------
; Register once in Inno Setup -> Tools -> Configure Sign Tools, e.g.:
;   Name: MySignTool   Command: "C:\Path\signtool.exe" sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 $f
; Then compile with:  iscc /DSignToolName="MySignTool" installer.iss
#ifdef SignToolName
SignTool={#SignToolName}
SignedUninstaller=yes
#endif

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\MeshForge3D\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
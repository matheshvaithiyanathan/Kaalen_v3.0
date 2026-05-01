; -- Kaalen_Installer.iss --
; Fixes:
; 1. Uses a static AppId to prevent duplicate "Programs and Features" entries.
; 2. Uses [Registry] with 'deletekey' flag to forcefully remove the old, broken registry entry ("Kaalen Data Viewer 1.0") DURING INSTALLATION.

[Setup]
; --- Application Identity ---
AppName=Kaalen     
AppVersion=2.0
AppPublisher=Mathesh Vaithiyanathan
VersionInfoCompany=Mathesh Vaithiyanathan (Author)

; *** CRITICAL FIX: The AppId must be static across all versions (v1.0, v2.0, etc.) ***
; This ensures that upgrading replaces the previous entry instead of adding a new one.
AppId={{50E0D2F8-3A7B-46C9-A1C8-710E1C92E152} 

; --- Installation Paths ---
DefaultDirName={autopf}\Kaalen
DefaultGroupName=Kaalen
AllowNoIcons=yes
OutputDir=Output_Installer
OutputBaseFilename=Kaalen_Setup_v2.0
Compression=lzma
SolidCompression=yes
SetupIconFile=icon.ico
WizardStyle=modern

; --- CRITICAL FIX: CLEANUP FOR BROKEN V1.0 REGISTRY ENTRY ---
; We move the cleanup logic to the [Registry] section and use the 'deletekey' flag
; which executes the deletion when the installer runs (line 33 in your previous script).
[Registry]
; This entry deletes the old, manual registry subkey used by the V1.0 installer.
; We use 'none' as ValueType because we only want to delete the key, not create a value.
Root: "HKLM"; Subkey: "SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Kaalen_App"; ValueType: "none"; Flags: deletekey;

[Files]
; This command copies all files (recursively) from the PyInstaller build directory
Source: "dist\Kaalen_App\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Creates a Start Menu shortcut
Name: "{group}\Kaalen"; Filename: "{app}\Kaalen_App.exe"; IconFilename: "{app}\Kaalen_App.exe"; WorkingDir: "{app}"
; Creates an optional Desktop shortcut
Name: "{autodesktop}\Kaalen"; Filename: "{app}\Kaalen_App.exe"; IconFilename: "{app}\Kaalen_App.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}";

;[Run]
;Filename: "{app}\Kaalen_App.exe"; Description: "{cm:LaunchProgram,Kaalen}"; Flags: nowait postinstall skipifdoesntexist

; *** IMPORTANT ***
; The manual [Registry] section from your previous script that created the duplicate
; "Kaalen Data Viewer 1.0" entry is now completely removed, as AppId handles this automatically.

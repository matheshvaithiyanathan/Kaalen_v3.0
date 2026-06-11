[Setup]
AppName=Kaalen v3
AppVersion=3.0
AppPublisher=InstrumentsResponse
AppCopyright=Copyright (C) 2026 InstrumentsResponse
VersionInfoCompany=InstrumentsResponse
AppId={{50E0D2F8-3A7B-46C9-A1C8-710E1C92E152}
DefaultDirName={autopf}\Kaalen v3
DefaultGroupName=Kaalen v3
AllowNoIcons=yes
OutputDir=Output_Installer
OutputBaseFilename=Kaalen_v3_windows_Setup
Compression=lzma
SolidCompression=yes
SetupIconFile=icon.ico
WizardStyle=modern

[Registry]
Root: "HKLM"; Subkey: "SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Kaalen_v3"; ValueType: "none"; Flags: deletekey;

[Files]
Source: "dist\Kaalen_v3\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Kaalen v3"; Filename: "{app}\Kaalen_v3.exe"; IconFilename: "{app}\Kaalen_v3.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\Kaalen v3"; Filename: "{app}\Kaalen_v3.exe"; IconFilename: "{app}\Kaalen_v3.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}";

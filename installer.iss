#define AppName "RF4Club Sync"
#ifndef AppVersion
  #define AppVersion "1.1.0"
#endif
#define AppPublisher "RF4Club"
#define AppURL "https://rf4club.com"
#ifndef SourceDir
  #define SourceDir "dist\RF4Club Sync"
#endif

[Setup]
AppId={{9A7D5343-5C72-4CA4-B94D-FB803297BBE1}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
DefaultDirName={localappdata}\Programs\RF4Club Sync
DefaultGroupName=RF4Club Sync
OutputDir=release
OutputBaseFilename=RF4Club-Sync-Setup-v{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
UninstallDisplayName=RF4Club Sync
LicenseFile=LICENSE

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "NOTICE"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\RF4Club Sync"; Filename: "{app}\RF4Club Sync.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\RF4Club Sync"; Filename: "{app}\RF4Club Sync.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Masaüstü kısayolu oluştur"; GroupDescription: "Kısayollar:"; Flags: checkedonce

[Run]
Filename: "{app}\RF4Club Sync.exe"; Description: "RF4Club Sync'i başlat"; Flags: nowait postinstall skipifsilent

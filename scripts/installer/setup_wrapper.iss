[Setup]
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\NRA-Metadata.exe
UninstallDisplayName=NRA Metadata
AppPublisher=NRA
AppId={{E8B62589-9A0B-4D1C-8A3E-9F93F16A9123}
CreateUninstallRegKey=yes
DirExistsWarning=no
DefaultDirName={commonpf}\NRA-Metadata
SetupIconFile=app.ico
Uninstallable=yes
AppName=NRA Metadata
AppVersion=1.2.0
CreateAppDir=yes
PrivilegesRequired=admin
OutputDir=..\..\dist
OutputBaseFilename=NRA-Metadata-Setup-Final
Compression=lzma2/fast
SolidCompression=no
DisableDirPage=yes
DisableProgramGroupPage=yes

[Files]
Source: "..\..\dist\Setup-GUI\*"; DestDir: "{tmp}\Setup-GUI"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\..\dist\NRA-Metadata-Installer\payload.dat"; DestDir: "{tmp}\Setup-GUI"; Flags: ignoreversion

[Run]
Filename: "{tmp}\Setup-GUI\Setup.exe"; WorkingDir: "{tmp}\Setup-GUI"; Flags: waituntilterminated skipifsilent
[UninstallDelete]
Type: filesandordirs; Name: "{app}"
Type: filesandordirs; Name: "{localappdata}\NRA-Metadata"
Type: filesandordirs; Name: "{userdesktop}\NRA-Metadata.lnk"
Type: filesandordirs; Name: "{commonprograms}\NRA-Metadata.lnk"
Type: filesandordirs; Name: "{userprograms}\NRA-Metadata.lnk"


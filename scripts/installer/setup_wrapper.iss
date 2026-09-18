[Setup]
AppName=NRA Metadata
AppVersion=1.0.0
CreateAppDir=no
PrivilegesRequired=admin
OutputDir=..\..\dist
OutputBaseFilename=NRA-Metadata-Setup-Final
Compression=lzma2/ultra64
SolidCompression=yes
DisableDirPage=yes
DisableProgramGroupPage=yes

[Files]
Source: "..\..\dist\Setup-GUI\*"; DestDir: "{tmp}\Setup-GUI"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\..\dist\NRA-Metadata-Installer\payload.dat"; DestDir: "{tmp}"; Flags: ignoreversion

[Run]
Filename: "{tmp}\Setup-GUI\Setup.exe"; Flags: waituntilterminated skipifsilent
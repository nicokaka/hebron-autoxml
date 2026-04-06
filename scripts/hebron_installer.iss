[Setup]
AppName=HebronAutoXML
AppVersion=1.0.0
AppPublisher=Hebron Contabilidade
DefaultDirName={autopf}\HebronAutoXML
DefaultGroupName=HebronAutoXML
DisableProgramGroupPage=yes
OutputBaseFilename=HebronSetup
OutputDir=..\Output
Compression=lzma
SolidCompression=yes
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\HebronAutoXML.exe
PrivilegesRequired=lowest

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\HebronAutoXML\HebronAutoXML.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\HebronAutoXML\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\HebronAutoXML"; Filename: "{app}\HebronAutoXML.exe"; IconFilename: "{app}\HebronAutoXML.exe"
Name: "{group}\{cm:UninstallProgram,HebronAutoXML}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\HebronAutoXML"; Filename: "{app}\HebronAutoXML.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\HebronAutoXML.exe"; Description: "{cm:LaunchProgram,HebronAutoXML}"; Flags: nowait postinstall skipifsilent

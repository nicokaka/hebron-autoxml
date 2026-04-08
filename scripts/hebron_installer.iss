[Setup]
AppName=HebronAutoXML
AppVersion=3.1.0
AppPublisher=Hebron Contabilidade
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
DefaultDirName={autopf}\HebronAutoXML
DefaultGroupName=HebronAutoXML
DisableProgramGroupPage=yes
OutputBaseFilename=HebronAutoXML_v3.1_Setup
OutputDir=..\Output
Compression=lzma
SolidCompression=yes
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\HebronAutoXML.exe
PrivilegesRequired=lowest
WizardStyle=modern

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

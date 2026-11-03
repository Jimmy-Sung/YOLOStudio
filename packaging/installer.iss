#ifndef PayloadDir
  #error Supply /DPayloadDir=absolute-path
#endif
#ifndef ReleaseDir
  #error Supply /DReleaseDir=absolute-path
#endif
#define AppVersion "0.3.1"

[Setup]
AppId={{7E80C571-55E0-4F1F-A75C-B3C63A8C3C35}
AppName=YOLO Studio
AppVersion={#AppVersion}
AppPublisher=YOLO Studio
AppComments=Native image annotation and CPU YOLO training. Python and PyTorch included.
DefaultDirName={localappdata}\Programs\YOLO Studio
DefaultGroupName=YOLO Studio
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.19045
OutputDir={#ReleaseDir}
OutputBaseFilename=YOLO-Studio-{#AppVersion}-Windows-x64-CPU-Setup
SetupIconFile={#PayloadDir}\app\assets\app-icon.ico
UninstallDisplayIcon={app}\YOLO Studio.exe
WizardStyle=modern
Compression=lzma2/fast
SolidCompression=yes
CloseApplications=yes
RestartApplications=no
SetupLogging=yes
DisableProgramGroupPage=yes
UninstallDisplayName=YOLO Studio (CPU training)

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "traditionalchinese"; MessagesFile: "compiler:Languages\ChineseTraditional.isl"
Name: "simplifiedchinese"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#PayloadDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\YOLO Studio"; Filename: "{app}\YOLO Studio.exe"; WorkingDir: "{app}"; IconFilename: "{app}\app\assets\app-icon.ico"
Name: "{autodesktop}\YOLO Studio"; Filename: "{app}\YOLO Studio.exe"; WorkingDir: "{app}"; IconFilename: "{app}\app\assets\app-icon.ico"; Tasks: desktopicon
Name: "{group}\Uninstall YOLO Studio"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\YOLO Studio.exe"; Description: "{cm:LaunchProgram,YOLO Studio}"; Flags: nowait postinstall skipifsilent

; User projects are under LocalAppData\YOLOStudio\data and intentionally
; never appear in UninstallDelete or application payload entries.

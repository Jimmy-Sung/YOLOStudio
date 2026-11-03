#ifndef PayloadDir
  #error Supply /DPayloadDir
#endif
#ifndef ReleaseDir
  #error Supply /DReleaseDir
#endif

[Setup]
AppId={{7E80C571-55E0-4F1F-A75C-B3C63A8C3C35}
AppName=YOLO Studio
AppVersion=0.3.1
AppPublisher=YOLO Studio
AppComments=Automatic NVIDIA CUDA 12.8 / CUDA 12.6 / CPU selection. Python and PyTorch included.
DefaultDirName={localappdata}\Programs\YOLO Studio
DefaultGroupName=YOLO Studio
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.19045
OutputDir={#ReleaseDir}
OutputBaseFilename=YOLO-Studio-0.3.1-Windows-x64-AutoCUDA-Setup
SetupIconFile={#PayloadDir}\app\assets\app-icon.ico
UninstallDisplayIcon={app}\YOLO Studio.exe
WizardStyle=modern
Compression=lzma2/fast
SolidCompression=yes
DiskSpanning=yes
DiskSliceSize=1566000000
CloseApplications=yes
RestartApplications=no
SetupLogging=yes
DisableProgramGroupPage=yes
UninstallDisplayName=YOLO Studio (Auto CUDA / CPU)

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "traditionalchinese"; MessagesFile: "compiler:Languages\ChineseTraditional.isl"
Name: "simplifiedchinese"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[CustomMessages]
english.EngineSummary=Automatically selected training engine: %1
english.EngineDetails=NVIDIA GPU, compute capability and driver checked. CPU is always available.
traditionalchinese.EngineSummary=自動選用的訓練引擎：%1
traditionalchinese.EngineDetails=已檢查 NVIDIA 顯卡、運算能力與驅動，並保留 CPU 引擎。
simplifiedchinese.EngineSummary=自动选用的训练引擎：%1
simplifiedchinese.EngineDetails=已检查 NVIDIA 显卡、计算能力与驱动，并保留 CPU 引擎。

[Files]
Source: "{#PayloadDir}\GpuDetect.exe"; Flags: dontcopy
Source: "{#PayloadDir}\engine-catalog.json"; Flags: dontcopy
Source: "{#PayloadDir}\*"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#PayloadDir}\app\*"; DestDir: "{app}\app"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#PayloadDir}\runtime\*"; DestDir: "{app}\runtime"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#PayloadDir}\licenses\*"; DestDir: "{app}\licenses"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#PayloadDir}\engines\cu126\*"; DestDir: "{app}\engines\cu126"; Flags: ignoreversion recursesubdirs createallsubdirs; Check: Use126
Source: "{#PayloadDir}\engines\cu128\*"; DestDir: "{app}\engines\cu128"; Flags: ignoreversion recursesubdirs createallsubdirs; Check: Use128

[Icons]
Name: "{group}\YOLO Studio"; Filename: "{app}\YOLO Studio.exe"; WorkingDir: "{app}"; IconFilename: "{app}\app\assets\app-icon.ico"
Name: "{autodesktop}\YOLO Studio"; Filename: "{app}\YOLO Studio.exe"; WorkingDir: "{app}"; IconFilename: "{app}\app\assets\app-icon.ico"; Tasks: desktopicon
Name: "{group}\Uninstall YOLO Studio"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\YOLO Studio.exe"; Description: "{cm:LaunchProgram,YOLO Studio}"; Flags: nowait postinstall skipifsilent

[Code]
var
  Engine: String;
  DetectionDone: Boolean;

procedure DetectEngine;
var
  Code: Integer;
  Path, Params: String;
  Value: AnsiString;
begin
  if DetectionDone then exit;
  DetectionDone := True;
  Engine := 'cpu';
  ExtractTemporaryFile('GpuDetect.exe');
  ExtractTemporaryFile('engine-catalog.json');
  Path := ExpandConstant('{tmp}\selected-engine.txt');
  Params := '--catalog "' + ExpandConstant('{tmp}\engine-catalog.json') + '" --allow-uninstalled --output "' + Path + '"';
  if Exec(ExpandConstant('{tmp}\GpuDetect.exe'), Params, '', SW_HIDE, ewWaitUntilTerminated, Code) and (Code = 0) then
    if LoadStringFromFile(Path, Value) then
      if (Trim(Value) = 'cu126') or (Trim(Value) = 'cu128') then Engine := Trim(Value);
  Log('Automatically selected training engine: ' + Engine);
end;

function Use126: Boolean;
begin
  DetectEngine;
  Result := Engine = 'cu126';
end;

function Use128: Boolean;
begin
  DetectEngine;
  Result := Engine = 'cu128';
end;

procedure InitializeWizard;
begin
  DetectEngine;
end;

function UpdateReadyMemo(Space, NewLine, MemoUserInfoInfo, MemoDirInfo, MemoTypeInfo,
  MemoComponentsInfo, MemoGroupInfo, MemoTasksInfo: String): String;
begin
  Result := MemoDirInfo + NewLine + NewLine + FmtMessage(CustomMessage('EngineSummary'), [Engine]) + NewLine +
    CustomMessage('EngineDetails');
end;

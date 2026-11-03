# YOLO Studio 0.2.0 安裝與離線使用

## 適用環境

- Windows 10 22H2 / Windows 11，64 位元 x64 電腦。
- CPU 版包含 Python 3.12、PySide6 / Qt、Ultralytics YOLO、PyTorch CPU、torchvision，以及三個預訓練偵測模型。**不需要另裝 Python、pip、Torch 或 CUDA，也不使用目標電腦既有的 Python 環境。**
- 已包含 Python 與 Qt 套件提供的 Visual C++ Runtime DLL。硬體仍需符合隨附 PyTorch / Qt 的要求。
- 這不是 macOS / Linux / Windows ARM 原生安裝包。這些平台需要各自建置與驗證。

## 安裝

1. 執行 `YOLO-Studio-0.2.0-Windows-x64-CPU-Setup.exe`，選繁體中文、簡體中文或英文。
2. 預設安裝在目前使用者的 `%LOCALAPPDATA%\Programs\YOLO Studio`，不需要系統管理員權限。
3. 從開始選單或桌面捷徑開啟 YOLO Studio。

如果收到 Windows 對未簽署程式的提示，請先由組織的 IT 確認套件來源。此測試版本沒有購買商業程式碼簽章憑證。

## 圖片、專案與模型

安裝版的工作資料存放在 `%LOCALAPPDATA%\YOLOStudio\data`。安裝與程式檔案分離，升級及移除程式不會刪除此資料夾。請停止程式後再備份或搬移資料。

安裝包不包含開發電腦上的專案、照片及訓練紀錄。若要將原開發版資料搬到安裝版，先停止兩邊程式，再備份及複製原 `data` 資料夾內容到上述位置；不要直接覆蓋另一套已在使用中的專案資料。

## 離線訓練

YOLO11n、YOLO11s 與 YOLOv10n 預訓練權重已包含在 `app/models/`。手動標註、自動標註及 CPU 訓練可在離線環境執行。新匯入的自訂 `.pt` 模型也可直接使用。

CPU 版的「自動選擇」會使用 CPU；GPU 0 不適用此版本。NVIDIA GPU 加速需要另行製作 CUDA 版安裝包，並在目標電腦安裝相容的 NVIDIA 驅動；CPU 版不會自動改成 CUDA 版。

## 診斷

安裝資料夾的 `Check environment.cmd` 會檢查內建的 Python、Torch、torchvision、Qt 與預訓練模型，將結果寫入 `%LOCALAPPDATA%\YOLOStudio\environment-report.json`。

`distribution.json`、`packages.lock.txt` 及 `licenses/` 記錄隨附版本與第三方授權資訊；第三方套件原有的授權檔也保留在 runtime 的套件 metadata 中。Ultralytics 的授權條件適用於其套件與權重；本套件同時包含應用程式原始碼，便於檢查。

此版本是在建置電腦隔離、重新安裝到不同路徑後驗證；尚未在所有 Windows 版本與硬體上測試。

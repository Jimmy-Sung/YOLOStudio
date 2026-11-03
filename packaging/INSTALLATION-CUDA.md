# YOLO Studio 0.3.0 — 自動 CUDA / CPU 安裝包

適用 Windows 10 22H2 / Windows 11 x64。包含獨立 Python、介面、YOLO、CPU PyTorch，以及 CUDA 12.6、12.8 版 PyTorch / torchvision；不需另裝 Python、Torch 或 CUDA Toolkit。

## 安裝與自動選擇

請將 Setup.exe 與所有同名 `.bin` 放在同一個資料夾，執行 Setup.exe。安裝程式會透過 NVIDIA Driver API 讀取顯卡名稱、實際運算能力及驅動可支援的 CUDA API，並檢查所附 PyTorch 的已編譯架構。

- 優先選擇相容的 CUDA 12.8 引擎。
- 若驅動或架構不符合 12.8，但符合 12.6，則選 CUDA 12.6。
- 沒有 NVIDIA GPU、驅動太舊、硬體不在引擎支援範圍或偵測失敗時，使用 CPU。
- 同時有多張 GPU 時，選擇相容引擎中運算能力較高的 GPU。訓練裝置使用「自動選擇」。

這是保守的相容性策略：CUDA 12.8 要求驅動回報 API >=12.8，CUDA 12.6 要求 API >=12.6，不依賴有限制的跨小版本相容模式。顯卡的商品名稱本身不作為唯一依據。

安裝程式只安裝一套相容 CUDA 引擎，並始終保留 CPU。每次啟動會再檢查目前硬體與已安裝引擎；若之後更換顯卡或驅動，可能需要重新執行安裝程式，才能安裝另一套引擎。

NVIDIA 驅動屬於系統元件，**不會由本程式自動安裝或更新**。本套件只包含應用程式需要的 CUDA Runtime 與 cuDNN，並不是 CUDA 開發工具組。AMD / Intel GPU 目前使用 CPU。

## 資料與驗證

工作資料存放於 `%LOCALAPPDATA%\YOLOStudio\data`，升級或解除安裝不會刪除專案。安裝包不包含開發電腦上的任何專案或照片。原有 CPU 版安裝包另外保留。

側邊欄會顯示選用的 CUDA / CPU 引擎與 GPU 名稱。自動模式若 GPU 初始化或實際核心執行失敗，將改用 CPU；明確指定 GPU 時會顯示失敗原因。訓練版本中會保存實際使用的裝置、GPU 名稱及 Torch / CUDA 版本。

正式套件內含三個預訓練模型，可離線完成操作。第三方授權檔與版本清單保留在各 runtime 套件的 metadata。此版本不含商業程式碼簽章。

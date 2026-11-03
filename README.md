# YOLO Studio (LabelStudio) · Windows 原生視覺標註與模型訓練工作台

[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%2F%2011%20x64-blue.svg)](https://github.com/Jimmy-Sung/LabelStudio)
[![Python](https://img.shields.io/badge/Python-3.12-brightgreen.svg)](https://python.org)
[![UI](https://img.shields.io/badge/UI-PySide6%20%2F%20Qt%20Widgets-orange.svg)](https://doc.qt.io/qtforpython/)
[![Engine](https://img.shields.io/badge/Engine-Ultralytics%20YOLO%20%2B%20PyTorch-red.svg)](https://github.com/ultralytics/ultralytics)
[![License](https://img.shields.io/badge/License-Non--Commercial%20%2F%20Academic%20Only-lightgrey.svg)](#-版權與免責聲明-license--terms)

**YOLO Studio (LabelStudio)** 是一款專為 Windows 打造的輕量化、高效能 YOLO 原生桌面工作台。整合了**專案資料集管理**、**人工標註**、**AI 輔助標註**、**YOLO 模型訓練**、**測試評估指標計算**以及**模型匯出**之完整流程。

軟體基於 **Python + PySide6 / Qt 原生視窗架構**，無瀏覽器、無 Web 渲染負擔，具備極佳的介面響應速度與本機數據隱私安全性。

---

## 軟體下載 (Release Downloads)

我們提供編譯完成的 Windows 獨立安裝包（免預先安裝 Python 與依賴套件）：

> 📦 **安裝包下載頁面**：請至 [GitHub Releases](https://github.com/Jimmy-Sung/LabelStudio/releases) 下載最新安裝檔。

| 版本類型 | 適用環境 | 檔案組成與特點 | 推薦對象 |
| :--- | :--- | :--- | :--- |
| **Auto-CUDA (GPU 版)** | 具備 NVIDIA GeForce / RTX / GTX 獨立顯示卡之 Windows 電腦 | 包含主安裝程式與離線分片檔（`.exe` + `.bin`）。<br>內建 CUDA 12.6 與 12.8 雙離線加速引擎，自動偵測顯卡架構調度最適引擎，支援無 GPU 時自動平滑降級為 CPU。 | **強烈推薦**（訓練速度提升數十倍，支援混合精度 AMP） |
| **CPU 通用版** | 一般筆電、無 NVIDIA 獨立顯卡之電腦 | 單一安裝執行檔（`YOLO-Studio-x.x.x-Windows-x64-CPU-Setup.exe`，約 330 MB）。<br>隨裝即用，免任何環境配置。 | 一般測試、辦公電腦或輕量數據標註 |

> **GPU 安裝包使用說明**：
> 請將 `YOLO-Studio-*-AutoCUDA-Setup.exe` 與所有分片檔案（`*-Setup-1.bin` 至 `*-Setup-4.bin`）下載放置於**同一資料夾**中，雙擊執行 `.exe` 即可自動完成解壓與安裝。

---

## 核心功能特色

- 🎯 **流暢的人工標註體驗**
  - 原生 Qt 畫布，支援高解析度大圖平移、快速縮放、十字準星輔助線。
  - 支援快速鍵（`B` 畫框、`V` 選取/微調、`Delete` 刪框、`Ctrl+Z` 復原）。
  - 自動防呆與草稿自動保存機制，防止標註數據遺失。

- 🤖 **AI 自動候選標註與審核流程**
  - 支援載入內建預訓練模型或先前訓練出的自訂模型進行批次推論。
  - 推論結果以虛線候選框呈現，經由人工審核「確認並儲存」或「標記無目標」後方可納入訓練集，杜絕模型自我幻覺。

- ⚡ **雙模式自適應訓練（GPU 自動降級 CPU）**
  - 訓練設備預設優先使用 GPU（CUDA），無需繁瑣設定。
  - 當主機無相容 GPU 時，自動無縫降級為 CPU 訓練，流程不中斷、不跳錯誤。
  - 軟體重啟時自動清理殘留的背景訓練進程，釋放顯存並確保環境乾淨。

- 🖼️ **資料集管理與預處理工具**
  - 圖片去重、EXIF 自動旋轉校正、壞圖與破損檢測。
  - 內建影像增強與預處理（旋轉、翻轉、灰階、自動對比度、亮度調整、像素精確裁切），標註框同步連動變換。

- 📊 **嚴謹評估與一鍵匯出**
  - 每次訓練自動依比例（如 7:2:1）凍結獨立資料集快照。
  - 訓練完成自動於保留測試集計算 Precision、Recall、mAP@50、mAP@50-95 指標。
  - 支援一鍵匯出標準 YOLO 格式資料集與含有完整訓練日誌、類別定義之 `.pt` 模型套件。

---

## 原始碼本機運行 (Source Code Setup)

若您希望從原始碼執行或進行二次開發：

### 1. 取得專案原始碼
```bash
git clone https://github.com/Jimmy-Sung/LabelStudio.git
cd LabelStudio
```

### 2. 環境安裝 (Windows PowerShell)
```powershell
# 建立專屬虛擬環境並安裝基本依賴
powershell -ExecutionPolicy Bypass -File .\setup.ps1

# 若需要完整 YOLO 訓練與 PyTorch 引擎
powershell -ExecutionPolicy Bypass -File .\setup.ps1 -WithYolo
```

### 3. 啟動軟體
- 直接雙擊目錄下的 `YOLO Studio.exe`（原生啟動器，不開啟黑視窗）
- 或透過終端執行：
  ```powershell
  powershell -ExecutionPolicy Bypass -File .\start.ps1
  ```

---

## ⚠️ 版權與免責聲明 (License & Terms)

本專案之程式碼、架構設計與隨附安裝工具僅供**個人學習、學術研究、教學展示與技術參考**使用：

1. **禁止商用**：本軟體及其衍生物嚴禁直接或間接用於任何商業營利行為、企業生產線收費服務或未經授權之商業產品集成。
2. **免責條款**：本軟體按「現狀」（As-Is）提供，作者不對使用本軟體所產生之任何數據遺失、設備故障或商業損失承擔任何法律責任。
3. 若需在學術論文、研究報告或展示中引用本專案，請註明專案出處來源。

---

## 聯絡與支援

如有問題回報或學術交流需求，歡迎至 [GitHub Issues](https://github.com/Jimmy-Sung/LabelStudio/issues) 提出討論。

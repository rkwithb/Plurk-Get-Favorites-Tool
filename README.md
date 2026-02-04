# Plurk Favorite Archive (噗浪喜愛噗文備份工具)

[繁體中文] | [English](./README_en.md) | [日本語](./README_jp.md)

這是一個專為噗浪（Plurk）使用者開發的**深度備份工具**。它可以將個人帳號中所有的「喜愛噗文」完整抓取，並產生一個具備磨砂玻璃質感的視覺化網頁介面，方便自己隨時離線瀏覽。

---

## ✨ 核心特色
- **🚀 零設定啟動**：不需要安裝 Python 或自行申請 API Keys，直接下載執行檔即可運作。
- **💎 極致視覺體驗**：產出的備份網頁採用現代化 UI 設計，針對電腦版瀏覽器進行最佳化。
- **🔒 安全防護**：核心 Keys 初始階段以靜態寫入（Static Hardcoding），個人帳號存取權限僅儲存在電腦端。
- **📂 自動化整理**：系統會自動依月份分類儲存，並支援「不重覆備份」（每次僅抓取新的噗文）。

---

## 📥 下載與使用說明

### 1. 取得工具
請前往 [Releases](https://github.com/rkwithb/Plurk-Get-Favorites-Tool/releases) 頁面下載對應個人作業系統的執行檔：
- **Windows**: 下載 `Plurk_Archive_Win.exe`
- **macOS**: 下載 `Plurk_Archive_Mac`

### 2. 開始進行備份
1. 執行程式後，請依照畫面提示前往噗浪官網進行授權。
2. 將授權完成後取得的驗證碼（Verifier）貼回程式視窗。
3. 程式將自動建立 `backup_js` 資料夾並開始同步資料。

### 3. 瀏覽備份內容
備份完成後，直接開啟專案根目錄下的 `index.html` 即可開始瀏覽自己的最愛清單。

---

## ❓ 疑難排解 (Troubleshooting)

### 🍎 macOS 使用者無法開啟程式？
由於本工具為個人開發專案，未經過 Apple 官方付費簽署，因此在 macOS 執行時會出現「無法驗證開發者」的安全性警告。請依照以下步驟手動開啟權限：
1. 在 `Plurk_Archive_Mac` 檔案上點擊 **滑鼠右鍵**。
2. 選擇選單最上方的 **「開啟」**。
3. 在隨後彈出的系統視窗中，再次點擊 **「開啟」** 即可正常執行。

### 📱 如何在手機上瀏覽備份？
如果自己希望在手機上查看備份，建議將產出的檔案（`index.html`、`backup_js` 資料夾等）上傳至以下免費的靜態網頁託管空間：
- [Vercel](https://vercel.com/) (推薦：直接將資料夾拖放至網頁即可完成佈署)
- [Cloudflare Pages](https://pages.cloudflare.com/)
- [GitHub Pages](https://pages.github.com/)

---

## 🛠 深度開發資訊 (For Developers)
如果希望自行修改原始碼或重新編譯：
1. Clone 本專案至自己的電腦。
2. 執行 `pip install -r requirements.txt` 安裝必要的相依套件。
3. 在自己的 GitHub 儲存庫設定中，於 Secrets 填入 `PLURK_CONSUMER_KEY` 等資訊。
4. 透過推送 Git Tag（例如 `v1.0.0`）來觸發 GitHub Actions 的自動化建置流程。

---

## 📜 免責聲明
本工具僅供個人技術研究與資料備份使用，請務必遵守噗浪官方之 API 使用規範。

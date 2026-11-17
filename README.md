# Project Alpha-Guard: AI 量化情報與半自動交易決策平台

建基於 **Proxmox VE (PVE) + Docker + Tiger OpenAPI + Gemini AI** 的個人／內部半自動投資決策網頁系統。

## 核心設計原則
1. **AI 負責情報過濾與計算**：自動抓取持倉新聞與指標，輸出結構化分析報告。
2. **硬性風控寫死於底層**：強制限制只落限價單（Limit Order）、禁止無授權孖展負結餘、單一股票佔總資產上限 50%。
3. **Human-in-the-Loop（人機協同）**：所有買賣訊號必須經決策者於加密內網網頁手動點擊「批准」方可發送至券商。

## 快速部署（PVE Ubuntu VM）
1. 複製環境變數範本：`cp .env.example .env`
2. 填入 `GEMINI_API_KEY`（初期保持 `MOCK_MODE=True` 即可預覽完整介面）。
3. 啟動容器：`docker compose up -d --build`
4. 透過 Tailscale 內網 IP 存取：`http://<VM-Tailscale-IP>:8501`
import uuid
import pandas as pd
import streamlit as st

from app.config import Config
from app.database import (
    init_db,
    create_pending_order,
    get_orders,
    update_order_status,
    get_recent_audits,
    log_audit,
)
from app.broker_client import BrokerClient
from app.risk_engine import validate_order_risk
from app.ai_analyst import analyze_stock_with_gemini
from app.notifier import send_telegram_alert

st.set_page_config(
    page_title="Project Alpha-Guard | AI 量化情報與風控台",
    page_icon="🛡️",
    layout="wide",
)

init_db()
broker = BrokerClient()

# === 頂部安全狀態橫幅 ===
env_badge = "🟡 SANDBOX 模擬盤模式" if Config.TRADING_ENV == "SANDBOX" else "🔴 PROD 實盤交易模式"
mock_badge = " | 🧪 DEMO 模擬數據中" if Config.MOCK_MODE else " | 🔗 已連接 Tiger OpenAPI"
st.title("🛡️ Project Alpha-Guard — AI 投資情報與半自動決策平台")
st.caption(f"當前環境：**{env_badge}{mock_badge}** ｜ 單一持倉硬性上限：**{Config.MAX_SINGLE_STOCK_PCT*100:.0f}%** ｜ 執行模式：**強制限價單＋人工審批**")

portfolio = broker.get_portfolio_summary()

# 四大核心功能分頁
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 1. 資產與槓桿風控儀表板",
    "🧠 2. AI 盤前情報與分析室",
    "🛡️ 3. 半自動訊號審批台",
    "📜 4. 審計與風控攔截日誌"
])

# ==========================================
# TAB 1: 綜合資產與槓桿風控儀表板
# ==========================================
with tab1:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("綜合賬戶總資產 (USD)", f"${portfolio['total_assets']:,.2f}")
    c2.metric("美股持倉總市值", f"${portfolio['stock_value']:,.2f}")
    c3.metric("貨幣基金儲備（老虎錢罌）", f"${portfolio['money_market_fund']:,.2f}")
    c4.metric(
        "實際無槓桿淨現金",
        f"${portfolio['net_available_cash']:,.2f}",
        delta=f"證券賬面結餘: ${portfolio['securities_cash']:,.2f}",
        delta_color="normal" if portfolio["securities_cash"] >= 0 else "inverse"
    )

    if portfolio["securities_cash"] < 0:
        st.warning(
            f"⚠️ **待交收／孖展提醒**：證券戶口目前顯示負結餘 **${portfolio['securities_cash']:,.2f}**。"
            f"請確認『自動申贖』是否已觸發交收，避免產生高息孖展息差。"
        )

    st.subheader("持倉集中度與風控監控")
    if portfolio["positions"]:
        df = pd.DataFrame(portfolio["positions"])
        df["佔總資產比例 (%)"] = (df["market_value"] / portfolio["total_assets"] * 100).round(2)
        df["風控狀態"] = df["佔總資產比例 (%)"].apply(
            lambda x: "🚨 已達上限（禁止加倉）" if x >= Config.MAX_SINGLE_STOCK_PCT * 100 else "✅ 正常範圍"
        )
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("目前無股票持倉。")

# ==========================================
# TAB 2: AI 盤前情報與分析室
# ==========================================
with tab2:
    st.subheader("AI 個股深度情報推理")
    col_a, col_b = st.columns([1, 2])
    with col_a:
        target_symbol = st.selectbox("選擇分析標的", Config.WATCHLIST)
        custom_symbol = st.text_input("或手動輸入美股代碼（如 AMD）", "").strip().upper()
        symbol_to_analyze = custom_symbol if custom_symbol else target_symbol
        user_note = st.text_area("補充最新市場消息／財報背景（選填）", placeholder="例如：明日盤後公佈 Q3 業績，近期受管理層變動影響回調...")
        run_ai = st.button("🚀 生成 AI 分析報告", type="primary")

    with col_b:
        if run_ai:
            with st.spinner(f"正在調用 Gemini AI 分析 {symbol_to_analyze}..."):
                price = broker.get_latest_price(symbol_to_analyze)
                pos = next((p for p in portfolio["positions"] if p["symbol"] == symbol_to_analyze), None)
                report = analyze_stock_with_gemini(symbol_to_analyze, price, pos, user_note)
                log_audit("AI_ANALYSIS", f"完成 {symbol_to_analyze} AI 分析（參考價 ${price:.2f}）", symbol_to_analyze)
                st.markdown(report)
        else:
            st.info("👈 請在左側選擇股票並點擊「生成 AI 分析報告」。")

# ==========================================
# TAB 3: 半自動訊號審批台 (Human-in-the-Loop)
# ==========================================
with tab3:
    st.subheader("建立待審批限價單草稿（必須經過五道硬性風控）")
    with st.form("create_signal_form"):
        f1, f2, f3, f4 = st.columns(4)
        sig_symbol = f1.text_input("股票代碼", value="NVDA").strip().upper()
        sig_action = f2.selectbox("買賣方向", ["BUY", "SELL"])
        sig_qty = f3.number_input("股數 (整股)", min_value=1, value=5, step=1)
        default_px = broker.get_latest_price(sig_symbol) or 150.0
        sig_price = f4.number_input("限價單價格 (USD)", min_value=0.01, value=float(round(default_px * 0.96, 2)), step=0.5)
        sig_reason = st.text_input("交易理據備註", value="回調至預設支持區間，分批限價吸納")
        submitted = st.form_submit_button("🔍 進行風控預檢並加入待審批隊列")

        if submitted:
            new_uuid = f"ORD-{uuid.uuid4().hex[:10].upper()}"
            passed, msg = validate_order_risk(
                order_uuid=new_uuid,
                symbol=sig_symbol,
                action=sig_action,
                quantity=int(sig_qty),
                limit_price=float(sig_price),
                order_type="LMT",
                portfolio=portfolio
            )
            if passed:
                create_pending_order(new_uuid, sig_symbol, sig_action, int(sig_qty), float(sig_price), sig_reason)
                send_telegram_alert(
                    f"🛡️ *Alpha-Guard 待審批訊號*\n"
                    f"標的：`{sig_symbol}` ({sig_action})\n"
                    f"數量：{sig_qty} 股 @ `${sig_price:.2f}`\n"
                    f"理據：{sig_reason}\n"
                    f"請登入內網網頁核准執行。"
                )
                st.success(f"✅ {msg}！已加入下方待審批隊列。")
            else:
                st.error(f"🛑 {msg}")

    st.divider()
    st.subheader("⏳ 待人工拍板訂單隊列（Pending Approval）")
    pending_orders = get_orders(status="PENDING")
    if not pending_orders:
        st.info("目前沒有等待審批的交易指令。")
    else:
        for ord_item in pending_orders:
            with st.container(border=True):
                oc1, oc2, oc3 = st.columns([3, 1, 1])
                total_amt = ord_item["quantity"] * ord_item["limit_price"]
                oc1.markdown(
                    f"**[{ord_item['order_uuid']}] {ord_item['action']} {ord_item['symbol']} — "
                    f"{ord_item['quantity']} 股 @ ${ord_item['limit_price']:.2f}**（總額：`${total_amt:,.2f}`）\n\n"
                    f"📝 理據：{ord_item['ai_reason']} ｜ 建立時間：{ord_item['created_at']}"
                )
                if oc2.button("✅ 批准並送出限價單", key=f"approve_{ord_item['order_uuid']}", type="primary"):
                    ok, recheck_msg = validate_order_risk(
                        order_uuid=ord_item["order_uuid"],
                        symbol=ord_item["symbol"],
                        action=ord_item["action"],
                        quantity=ord_item["quantity"],
                        limit_price=ord_item["limit_price"],
                        order_type="LMT",
                        portfolio=portfolio
                    )
                    if ok:
                        broker_id = broker.execute_limit_order(
                            ord_item["symbol"], ord_item["action"], ord_item["quantity"], ord_item["limit_price"]
                        )
                        update_order_status(ord_item["order_uuid"], "EXECUTED", broker_id)
                        st.success(f"🎉 訂單已送出！券商單號：{broker_id}")
                        st.rerun()
                    else:
                        st.error(f"🛑 複檢失敗：{recheck_msg}")

                if oc3.button("❌ 拒絕 / 作廢", key=f"reject_{ord_item['order_uuid']}"):
                    update_order_status(ord_item["order_uuid"], "REJECTED")
                    log_audit("ORDER_REJECTED", f"人工拒絕訂單 {ord_item['order_uuid']}", ord_item["symbol"])
                    st.rerun()

# ==========================================
# TAB 4: 審計與風控攔截日誌
# ==========================================
with tab4:
    st.subheader("歷史訂單執行記錄")
    all_orders = get_orders()
    if all_orders:
        st.dataframe(pd.DataFrame(all_orders), use_container_width=True, hide_index=True)

    st.subheader("系統風控攔截與操作審計日誌")
    audits = get_recent_audits(50)
    if audits:
        st.dataframe(pd.DataFrame(audits), use_container_width=True, hide_index=True)
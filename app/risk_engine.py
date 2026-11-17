from typing import Tuple, Dict, Any
from app.config import Config
from app.database import is_order_already_processed, log_audit

def validate_order_risk(
    order_uuid: str,
    symbol: str,
    action: str,
    quantity: int,
    limit_price: float,
    order_type: str,
    portfolio: Dict[str, Any]
) -> Tuple[bool, str]:
    """
    五道硬性風控閘門（寫死於 Python 底層，AI 無法繞過）：
    1. 環境安全確認
    2. 強制限價單（禁止市價單）
    3. 防重複落單檢查（Idempotency）
    4. 零孖展負結餘防線（Zero-Margin Guard）
    5. 單一股票集中度上限（預設 50%）
    """
    symbol = symbol.upper()
    action = action.upper()

    # 閘門 1：環境合法性
    if Config.TRADING_ENV not in ("SANDBOX", "PROD"):
        msg = f"攔截：非法運行環境 {Config.TRADING_ENV}"
        log_audit("RISK_BLOCK", msg, symbol)
        return False, msg

    # 閘門 2：只限限價單
    if order_type.upper() != "LMT" or limit_price <= 0 or quantity <= 0:
        msg = "攔截：系統強制只允許有效限價單（Limit Order），嚴禁市價單"
        log_audit("RISK_BLOCK", msg, symbol)
        return False, msg

    # 閘門 3：防重複執行
    if is_order_already_processed(order_uuid):
        msg = f"攔截：訂單 {order_uuid} 已被處理過，防止重複下單"
        log_audit("RISK_BLOCK", msg, symbol)
        return False, msg

    order_value = quantity * limit_price
    total_assets = portfolio.get("total_assets", 0.0)
    net_cash = portfolio.get("net_available_cash", 0.0)
    positions = portfolio.get("positions", [])

    if action == "BUY":
        # 閘門 4：零孖展防線（嚴禁動用負結餘借貸）
        if order_value > net_cash:
            msg = f"攔截（零孖展紅線）：買入金額 ${order_value:,.2f} 超過可用無槓桿淨現金 ${net_cash:,.2f}"
            log_audit("RISK_BLOCK", msg, symbol)
            return False, msg

        # 閘門 5：單一資產集中度上限
        current_symbol_val = sum(p["market_value"] for p in positions if p["symbol"] == symbol)
        projected_symbol_val = current_symbol_val + order_value
        projected_pct = (projected_symbol_val / total_assets) if total_assets > 0 else 1.0

        if projected_pct > Config.MAX_SINGLE_STOCK_PCT:
            msg = (
                f"攔截（集中度紅線）：買入後 {symbol} 市值將達 ${projected_symbol_val:,.2f} "
                f"（佔總資產 {projected_pct*100:.1f}%），超過上限 {Config.MAX_SINGLE_STOCK_PCT*100:.0f}%"
            )
            log_audit("RISK_BLOCK", msg, symbol)
            return False, msg

    elif action == "SELL":
        held_qty = sum(p["quantity"] for p in positions if p["symbol"] == symbol)
        if quantity > held_qty:
            msg = f"攔截（禁沽空紅線）：賣出股數 {quantity} 大於現有持倉 {held_qty} 股"
            log_audit("RISK_BLOCK", msg, symbol)
            return False, msg

    return True, "通過全部五道硬性風控檢查"
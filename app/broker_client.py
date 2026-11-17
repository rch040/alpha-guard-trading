import os
import uuid
from typing import Dict, Any
from app.config import Config
from app.database import log_audit

class BrokerClient:
    def __init__(self):
        self.mock_mode = Config.MOCK_MODE
        self.trade_client = None
        self.quote_client = None

        if not self.mock_mode:
            self._init_tiger_clients()

    def _init_tiger_clients(self):
        from tigeropen.tiger_open_config import TigerOpenClientConfig
        from tigeropen.common.util.signature_utils import read_private_key
        from tigeropen.trade.trade_client import TradeClient
        from tigeropen.quote.quote_client import QuoteClient

        if not os.path.exists(Config.TIGER_PRIVATE_KEY_PATH):
            raise FileNotFoundError(f"找不到老虎私鑰檔案：{Config.TIGER_PRIVATE_KEY_PATH}")

        is_sandbox = (Config.TRADING_ENV == "SANDBOX")
        client_config = TigerOpenClientConfig(sandbox_debug=is_sandbox)
        client_config.private_key = read_private_key(Config.TIGER_PRIVATE_KEY_PATH)
        client_config.tiger_id = Config.TIGER_ID
        client_config.account = Config.TIGER_ACCOUNT
        client_config.license = Config.TIGER_LICENSE

        self.trade_client = TradeClient(client_config)
        self.quote_client = QuoteClient(client_config)

    def get_portfolio_summary(self) -> Dict[str, Any]:
        """讀取綜合賬戶資產、現金、貨幣基金與持倉明細"""
        if self.mock_mode:
            # 模擬示範數據（方便首次部署即刻預覽介面與風控效果）
            positions = [
                {"symbol": "NVDA", "quantity": 40, "avg_cost": 164.00, "current_price": 161.20, "market_value": 6448.00, "pnl": -112.00},
                {"symbol": "TSLA", "quantity": 3, "avg_cost": 367.30, "current_price": 379.80, "market_value": 1139.40, "pnl": 37.50},
                {"symbol": "QQQ", "quantity": 1, "avg_cost": 624.85, "current_price": 669.20, "market_value": 669.20, "pnl": 44.35},
            ]
            stock_value = sum(p["market_value"] for p in positions)
            money_market_fund = 8000.00
            securities_cash = -2500.00  # 模擬待交收負結餘
            net_available_cash = money_market_fund + securities_cash
            total_assets = stock_value + net_available_cash
            return {
                "total_assets": round(total_assets, 2),
                "stock_value": round(stock_value, 2),
                "money_market_fund": round(money_market_fund, 2),
                "securities_cash": round(securities_cash, 2),
                "net_available_cash": round(net_available_cash, 2),
                "positions": positions,
            }

        # 實盤／沙盒 Tiger OpenAPI 調用
        assets = self.trade_client.get_prime_assets(account=Config.TIGER_ACCOUNT)
        raw_positions = self.trade_client.get_positions(account=Config.TIGER_ACCOUNT)

        sec_segment = assets.segments.get("S")
        fund_segment = assets.segments.get("F")

        sec_cash = float(sec_segment.cash_balance) if sec_segment else 0.0
        fund_val = float(fund_segment.net_liquidation) if fund_segment else 0.0
        total_assets = float(sec_segment.net_liquidation) + fund_val if sec_segment else 0.0

        positions = []
        stock_value = 0.0
        for p in raw_positions:
            mv = float(p.market_value)
            stock_value += mv
            positions.append({
                "symbol": p.contract.symbol,
                "quantity": int(p.quantity),
                "avg_cost": float(p.average_cost),
                "current_price": float(p.market_price),
                "market_value": mv,
                "pnl": float(p.unrealized_pnl),
            })

        return {
            "total_assets": round(total_assets, 2),
            "stock_value": round(stock_value, 2),
            "money_market_fund": round(fund_val, 2),
            "securities_cash": round(sec_cash, 2),
            "net_available_cash": round(fund_val + sec_cash, 2),
            "positions": positions,
        }

    def get_latest_price(self, symbol: str) -> float:
        symbol = symbol.upper()
        if self.mock_mode:
            mock_prices = {"NVDA": 161.20, "TSLA": 379.80, "QQQ": 669.20, "AAPL": 354.50}
            return mock_prices.get(symbol, 150.00)

        briefs = self.quote_client.get_stock_briefs([symbol])
        if not briefs.empty:
            return float(briefs.iloc[0]["latest_price"])
        return 0.0

    def execute_limit_order(self, symbol: str, action: str, quantity: int, limit_price: float) -> str:
        """正式發送限價單至 Tiger OpenAPI"""
        if self.mock_mode:
            fake_id = f"MOCK-{uuid.uuid4().hex[:8].upper()}"
            log_audit("ORDER_EXECUTED", f"[模擬模式] 已送出 {action} {quantity} 股 @ ${limit_price:.2f} (單號: {fake_id})", symbol)
            return fake_id

        from tigeropen.common.consts import OrderType, ActionType
        from tigeropen.common.util.contract_utils import stock_contract
        from tigeropen.common.util.order_utils import limit_order

        contract = stock_contract(symbol=symbol.upper(), currency="USD")
        act = ActionType.BUY if action.upper() == "BUY" else ActionType.SELL
        order = limit_order(
            account=Config.TIGER_ACCOUNT,
            contract=contract,
            action=act,
            quantity=quantity,
            limit_price=limit_price
        )
        self.trade_client.place_order(order)
        broker_id = str(order.id)
        log_audit("ORDER_EXECUTED", f"[{Config.TRADING_ENV}] 已送出 {action} {quantity} 股 @ ${limit_price:.2f} (單號: {broker_id})", symbol)
        return broker_id
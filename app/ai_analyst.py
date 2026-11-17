from google import genai
from app.config import Config

def analyze_stock_with_gemini(symbol: str, current_price: float, position_info: dict, user_context: str = "") -> str:
    """調用 Gemini AI 生成結構化投資分析簡報"""
    if not Config.GEMINI_API_KEY:
        return (
            f"### {symbol} 離線模擬分析（未配置 GEMINI_API_KEY）\n"
            f"- **現價參考：** ${current_price:.2f}\n"
            f"- **核心觀點：** 目前處於關鍵技術支持位附近，建議觀察成交量變化，嚴守單一持倉上限，避免於重大業績公佈前盲目追高。\n"
            f"- **建議操作區間：** 可於現價下方 3%–5% 設置分批限價單（Limit Order）。"
        )

    client = genai.Client(api_key=Config.GEMINI_API_KEY)
    prompt = f"""
    你是一位冷靜、嚴謹的華爾街量化分析師兼風控官。請用繁體中文（香港專業財經用語）分析以下美股標的：
    - 股票代碼：{symbol}
    - 當前市價：${current_price:.2f}
    - 賬戶現有持倉：{position_info if position_info else '目前無持倉'}
    - 補充市場背景：{user_context if user_context else '無特別補充，請按最新市場邏輯評估'}

    請輸出簡潔、具可操作性的 Markdown 分析報告，包含：
    1. **核心多空邏輯**（3 點以內，具體指出催化劑與風險點）
    2. **關鍵技術位與估值評估**
    3. **限價單部署建議**（明確建議「觀望」、「逢低限價吸納」或「逢高減持」，並給出合理限價區間，嚴禁建議全倉梭哈）
    """
    response = client.models.generate_content(
        model=Config.GEMINI_MODEL,
        contents=prompt,
    )
    return response.text
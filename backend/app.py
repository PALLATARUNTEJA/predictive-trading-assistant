import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from typing import Optional, List
import uvicorn

# Import modules using direct package references
from backend.scanner import get_market_analysis, fetch_data, calculate_indicators, detect_patterns
from backend.model import get_prediction, train_model
from backend.broker import get_portfolio_status, buy_stock, sell_stock, reset_portfolio
from backend.alerts import check_portfolio_safety

app = FastAPI(title="Predictive Trading Assistant API")

# Add CORS Middleware to allow requests from frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Active WebSocket connections
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                # If connection is dead, we'll clean it up
                pass

ws_manager = ConnectionManager()

# Input validation models
class BuyRequest(BaseModel):
    ticker: str
    amount: float
    stop_loss_pct: Optional[float] = 20.0

class SellRequest(BaseModel):
    ticker: str
    shares: Optional[float] = None

class TrainRequest(BaseModel):
    tickers: Optional[List[str]] = None

class SettingsRequest(BaseModel):
    drawdown_limit_pct: float

@app.get("/api/scan")
def scan_market(tickers: Optional[str] = Query(None)):
    """
    Scans specified stocks (or a default list) for indicators, patterns, and ML predictions.
    """
    if tickers:
        ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    else:
        # Default stocks to scan
        ticker_list = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META"]

    results = []
    for ticker in ticker_list:
        try:
            analysis = get_market_analysis(ticker)
            if not analysis:
                continue
                
            prediction = get_prediction(ticker)
            analysis["prediction"] = prediction["prediction"]
            analysis["confidence"] = prediction["confidence"]
            analysis["prediction_reason"] = prediction["reason"]
            
            results.append(analysis)
        except Exception as e:
            print(f"Error scanning {ticker}: {e}")
            
    return results

@app.get("/api/portfolio")
async def get_portfolio():
    """
    Fetches portfolio holdings, automatically runs stop-loss security checks,
    and returns current stats and active danger alerts.
    """
    try:
        # First, run stop-loss checks to see if we need to auto-exit any holding
        alerts = check_portfolio_safety()
        
        # Broadcast alerts via web sockets if any were triggered
        if alerts:
            for alert in alerts:
                await ws_manager.broadcast(alert)
                
        # Fetch current portfolio holdings (we need to download fresh prices for them)
        portfolio = get_portfolio_status()
        current_prices = {}
        for ticker in portfolio["holdings"].keys():
            df = fetch_data(ticker, period="1d")
            if not df.empty:
                current_prices[ticker] = float(df.iloc[-1]['Close'])
                
        # Re-fetch status with fresh real-time prices
        status = get_portfolio_status(current_prices)
        return {"portfolio": status, "alerts": alerts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/buy")
async def buy(request: BuyRequest):
    """
    Executes a purchase order with size constraints.
    """
    # Fetch current price
    df = fetch_data(request.ticker, period="1d")
    if df.empty:
        raise HTTPException(status_code=400, detail=f"Invalid ticker: {request.ticker} or could not fetch price.")
        
    price = float(df.iloc[-1]['Close'])
    result = buy_stock(
        ticker=request.ticker.upper(),
        price=price,
        cash_amount=request.amount,
        stop_loss_pct=request.stop_loss_pct
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["reason"])
        
    # Broadcast trade notification
    await ws_manager.broadcast({
        "type": "TRADE",
        "title": f"BOUGHT {request.ticker.upper()}",
        "message": f"Successfully purchased {result['trade']['shares']:.4f} shares of {request.ticker.upper()} at ${price:.2f}.",
        "timestamp": result["trade"]["timestamp"]
    })
    
    return result

@app.post("/api/sell")
async def sell(request: SellRequest):
    """
    Executes a sell order.
    """
    df = fetch_data(request.ticker, period="1d")
    if df.empty:
        raise HTTPException(status_code=400, detail=f"Could not fetch current price for {request.ticker}.")
        
    price = float(df.iloc[-1]['Close'])
    result = sell_stock(
        ticker=request.ticker.upper(),
        price=price,
        shares_to_sell=request.shares,
        reason="Manual Order"
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["reason"])
        
    # Broadcast trade notification
    await ws_manager.broadcast({
        "type": "TRADE",
        "title": f"SOLD {request.ticker.upper()}",
        "message": f"Successfully sold {result['trade']['shares']:.4f} shares of {request.ticker.upper()} at ${price:.2f}.",
        "timestamp": result["trade"]["timestamp"]
    })
    
    return result

@app.post("/api/reset")
def reset():
    """
    Resets the portfolio database.
    """
    return reset_portfolio()

@app.post("/api/settings")
def update_settings(request: SettingsRequest):
    """
    Updates the portfolio daily drawdown limit settings.
    """
    from backend.broker import update_drawdown_settings
    return update_drawdown_settings(request.drawdown_limit_pct)

@app.post("/api/train")
def train(request: TrainRequest):
    """
    Trains the ML Random Forest model.
    """
    result = train_model(request.tickers)
    return result

@app.get("/api/chart/{ticker}")
def get_chart_data(ticker: str, interval: Optional[str] = "1d", period: Optional[str] = "60d"):
    """
    Returns historical candlestick data for charts supporting multi-timeframes.
    """
    df = fetch_data(ticker, period=period, interval=interval)
    if df.empty:
        raise HTTPException(status_code=400, detail=f"Could not fetch data for ticker {ticker}")
        
    df = calculate_indicators(df)
    
    candles = []
    for idx, row in df.iterrows():
        # Handle time formats: Intraday uses Unix seconds, Daily uses YYYY-MM-DD
        if interval in ["1m", "2m", "5m", "15m", "30m", "60m", "1h"]:
            time_val = int(idx.timestamp())
        else:
            time_val = idx.strftime("%Y-%m-%d")
            
        candles.append({
            "time": time_val,
            "open": float(row['Open']),
            "high": float(row['High']),
            "low": float(row['Low']),
            "close": float(row['Close']),
            "volume": float(row['Volume']),
            "sma_20": float(row['SMA_20']) if 'SMA_20' in row else None,
            "sma_50": float(row['SMA_50']) if 'SMA_50' in row else None,
            "rsi": float(row['RSI_14']) if 'RSI_14' in row else None
        })
    return candles

@app.get("/api/tick/{ticker}")
def get_latest_tick(ticker: str, interval: Optional[str] = "1m"):
    """
    Returns the single absolute latest price tick.
    """
    df = fetch_data(ticker, period="1d", interval=interval)
    if df.empty:
        raise HTTPException(status_code=400, detail=f"Could not fetch tick for ticker {ticker}")
    latest = df.iloc[-1]
    idx = df.index[-1]
    
    if interval in ["1m", "2m", "5m", "15m", "30m", "60m", "1h"]:
        time_val = int(idx.timestamp())
    else:
        time_val = idx.strftime("%Y-%m-%d")
        
    return {
        "time": time_val,
        "open": float(latest['Open']),
        "high": float(latest['High']),
        "low": float(latest['Low']),
        "close": float(latest['Close']),
        "volume": float(latest['Volume'])
    }


@app.get("/api/explain/{ticker}")
def explain_market(ticker: str):
    """
    Generates a natural language market explanation.
    """
    df = fetch_data(ticker, period="60d", interval="1d")
    if df.empty or len(df) < 50:
        raise HTTPException(status_code=400, detail="Insufficient data to analyze.")
        
    df = calculate_indicators(df)
    df = detect_patterns(df)
    
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    
    # Generate insights based on indicators
    insights = []
    
    # 1. Price vs Moving Average
    if latest['Close'] > latest['SMA_20'] and latest['SMA_20'] > latest['SMA_50']:
        insights.append(f"• **Trend**: Strong **bullish** structure. Price is trading above both SMA 20 (${latest['SMA_20']:.2f}) and SMA 50 (${latest['SMA_50']:.2f}), confirming positive momentum.")
    elif latest['Close'] < latest['SMA_20'] and latest['SMA_20'] < latest['SMA_50']:
        insights.append(f"• **Trend**: Dominant **bearish** breakdown. Price is under the key moving averages, warning of potential further weakness.")
    else:
        insights.append(f"• **Trend**: Market is **consolidating**. Price is floating between short-term and long-term moving averages, suggesting temporary directionless range trading.")
        
    # 2. RSI analysis
    rsi = latest['RSI_14']
    if rsi > 70:
        insights.append(f"• **Momentum (RSI)**: RSI is in the **Overbought** zone at **{rsi:.1f}**. Historically, this indicates a high likelihood of a short-term cooling-off or pull-back period. Buying here carries elevated risk.")
    elif rsi < 30:
        insights.append(f"• **Momentum (RSI)**: RSI is in the **Oversold** zone at **{rsi:.1f}**. The asset is statistically undervalued here, indicating high potential for a bullish oversold bounce.")
    else:
        insights.append(f"• **Momentum (RSI)**: RSI is at **{rsi:.1f}**, showing standard neutral conditions with plenty of room to expand in either direction.")
        
    # 3. MACD analysis
    macd = latest['MACD']
    sig = latest['MACD_Signal']
    if macd > sig and prev['MACD'] <= prev['MACD_Signal']:
        insights.append("• **MACD Alert**: A bullish **MACD crossover** just occurred! The MACD line crossed above the signal line, suggesting buying momentum is accelerating.")
    elif macd < sig and prev['MACD'] >= prev['MACD_Signal']:
        insights.append("• **MACD Alert**: A bearish **MACD crossover** occurred. Momentum is shifting to the downside.")
    else:
        insights.append(f"• **MACD**: Currently {'above' if macd > sig else 'below'} the signal line, implying a {'bullish' if macd > sig else 'bearish'} posture.")
        
    # 4. Candlestick patterns & spikes
    pattern = latest['Pattern']
    spike = latest['Spike']
    if pattern != 'None':
        insights.append(f"• **Candle Pattern**: Detected **{pattern}**. This pattern suggests active market sentiment shifts at the current price level.")
    if spike != 'None':
        insights.append(f"• **Volatility Spike**: Detected **{spike}**! Daily parameters breached standard deviation averages, suggesting institutional volume or rapid news-driven reallocation.")

    # Conclude Recommendations
    recommendation = "HOLD / Neutral"
    if rsi < 35 or (macd > sig and latest['Close'] > latest['SMA_20']):
        recommendation = "ACCUMULATE (BUY) with stop-loss"
    elif rsi > 68 or (macd < sig and latest['Close'] < latest['SMA_20']):
        recommendation = "PROTECT PROFITS / EXIT (SELL)"
        
    markdown_content = f"### Market Explanation for {ticker.upper()}\n\n" + "\n".join(insights) + f"\n\n**Assistant Recommendation**: **{recommendation}**"
    
    return {"explanation": markdown_content, "recommendation": recommendation}

# WebSocket Endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            # We just wait for incoming client packets or keep it open.
            # Real-time notifications are pushed by our HTTP handlers
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)

class ChatRequest(BaseModel):
    message: str
    ticker: Optional[str] = "AAPL"

from fastapi import Header

@app.post("/api/chat")
def chat_with_assistant(request: ChatRequest, x_gemini_key: Optional[str] = Header(None)):
    """
    Personal Finance & Trading Assistant Bot (Friday).
    """
    import requests
    message = request.message
    ticker = request.ticker.upper()
    msg_lower = message.lower()

    # 0. Check if user provided their own free Gemini API Key
    if x_gemini_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={x_gemini_key}"
            prompt = (
                f"You are Friday, a smart personal finance and stock trading AI chatbot assistant for Tarun. "
                f"Answer the user's question: '{message}' in a highly professional, conversational tone. "
                f"Keep your response concise (2-3 sentences max) and format it beautifully with standard Markdown."
            )
            payload = {
                "contents": [{"parts": [{"text": prompt}]}]
            }
            res = requests.post(url, json=payload, timeout=6)
            if res.status_code == 200:
                data = res.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                return {"response": text}
            else:
                print(f"Gemini API error status {res.status_code}: {res.text}")
        except Exception as e:
            print(f"Gemini query error: {e}")

    
    # 1. Check for portfolio-specific queries
    if any(k in msg_lower for k in ["portfolio", "balance", "net worth", "cash", "how much money", "holdings", "profits", "p/l"]):
        try:
            status = get_portfolio_status()
            return {
                "response": f"Your **Tarun Tejas Portfolio** current stats:\n"
                            f"• **Net Asset Value**: ${status['total_value']:.2f}\n"
                            f"• **Cash Balance**: ${status['cash']:.2f}\n"
                            f"• **Holdings Value**: ${status['holdings_value']:.2f}\n"
                            f"• **Daily P/L**: ${status['total_value'] - 10000.00:+.2f} ({((status['total_value'] - 10000.00)/10000.00)*100:+.2f}%)"
            }
        except Exception as e:
            return {"response": "I couldn't load your portfolio ledger stats. Please try again."}

    # 2. Check for stock-specific queries (Should I buy/sell AAPL?)
    if any(k in msg_lower for k in ["buy", "sell", "should i", "predict", "analysis", "forecast"]) and any(t in msg_lower or ticker in msg_lower for t in ["aapl", "msft", "nvda", "tsla", "meta", "googl"]):
        # Find which ticker they are talking about
        target_ticker = ticker
        for t in ["AAPL", "MSFT", "NVDA", "TSLA", "META", "GOOGL"]:
            if t.lower() in msg_lower:
                target_ticker = t
                break
        try:
            analysis = get_market_analysis(target_ticker)
            prediction = get_prediction(target_ticker)
            pred_label = prediction["prediction"]
            confidence = prediction["confidence"] * 100
            
            return {
                "response": f"Here is my real-time forecast for **{target_ticker}**:\n"
                            f"• **Current Price**: ${analysis['price']:.2f} ({analysis['change']:+.2f}%)\n"
                            f"• **Trend**: {analysis['trend']} (RSI is {analysis['rsi']:.1f})\n"
                            f"• **ML Prediction (3d)**: Price will go **{pred_label}**\n"
                            f"• **Model Confidence**: {confidence:.1f}%\n"
                            f"• **My Suggestion**: " + (
                                f"Accumulate small portions of {target_ticker} with a 15% stop loss." if pred_label == "UP" and confidence > 52 
                                else f"Hold active positions or take partial profits."
                            )
            }
        except Exception as e:
            return {"response": f"I had trouble analyzing {target_ticker} real-time. Please make sure the stock ticker is valid."}

    # 3. Fallback to free Hugging Face API for general trading or coding questions
    try:
        payload = {
            "inputs": f"<|im_start|>system\nYou are a helpful personal finance and trading assistant. Keep your responses concise (2-3 sentences max).<|im_end|>\n<|im_start|>user\n{message}<|im_end|>\n<|im_start|>assistant\n",
            "parameters": {"max_new_tokens": 150, "temperature": 0.7}
        }
        res = requests.post("https://api-inference.huggingface.co/models/Qwen/Qwen2.5-7B-Instruct", json=payload, timeout=6)
        if res.status_code == 200:
            result = res.json()
            text = result[0]["generated_text"]
            if "assistant\n" in text:
                text = text.split("assistant\n")[-1].strip()
            # Clean up system instructions if leaked
            text = text.split("<|im_end|>")[0].strip()
            return {"response": text}
    except Exception as e:
        print(f"HF Inference chat API error: {e}")

    # 4. Local Rule-Based Expert system (Bulletproof local NLP)
    if "rsi" in msg_lower:
        return {"response": "RSI (Relative Strength Index) is a momentum indicator that ranges from 0 to 100. Traditionally, values above 70 indicate a stock is overbought (likely to decline), and values below 30 indicate it is oversold (likely to rise)."}
    elif "macd" in msg_lower:
        return {"response": "MACD is a trend-following momentum indicator. A buy signal is triggered when the MACD line crosses above the Signal line, while a sell signal occurs when it crosses below."}
    elif "stop loss" in msg_lower or "stoploss" in msg_lower:
        return {"response": "A Stop Loss is an automatic trigger to sell a position once it drops below a set price. This prevents heavy losses, protecting your cash balance."}
    elif "drawdown" in msg_lower:
        return {"response": "Drawdown measures the decline in your net worth from its peak. Our system automatically locks buying power if daily drawdown breaches 5%."}
    elif any(k in msg_lower for k in ["hello", "hi", "hey", "hola"]):
        return {"response": "Hello Tarun! I am your Personal Predictive Assistant. Ask me questions like 'Should I buy AAPL?', 'What is my current portfolio value?', or explainers like 'What is MACD?'"}
    
    return {
        "response": "I am currently monitoring the live stock market ticks. Ask me queries like 'What is my cash balance?', 'Analyze MSFT', or 'What does RSI mean?'"
    }

# Mount frontend static directory
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run("backend.app:app", host="127.0.0.1", port=8000, reload=True)



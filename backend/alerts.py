from backend.broker import load_portfolio, sell_stock, get_portfolio_status
from backend.scanner import fetch_data

def check_portfolio_safety() -> list:
    """
    Checks all active holdings in the portfolio against their stop-loss levels.
    Fetches real-time prices for each holding, updates the portfolio value,
    and automatically executes a SELL order if a stop-loss is breached.
    
    Returns:
        List of alert dictionaries describing executed exits.
    """
    portfolio = load_portfolio()
    holdings = portfolio.get("holdings", {})
    
    alerts = []
    if not holdings:
        return alerts
        
    for ticker, h in list(holdings.items()):
        # Fetch latest price
        df = fetch_data(ticker, period="1d", interval="1m")
        if df.empty:
            continue
            
        latest_price = float(df.iloc[-1]['Close'])
        stop_loss_val = float(h["stop_loss_val"])
        
        # Check stop-loss breach
        if latest_price <= stop_loss_val:
            print(f"[DANGER ALERT] Stop-loss breach on {ticker}! Current: ${latest_price:.2f}, Stop-Loss: ${stop_loss_val:.2f}. Executing automatic exit...")
            # Execute auto-exit
            sell_result = sell_stock(
                ticker=ticker,
                price=latest_price,
                shares_to_sell=h["shares"],
                reason="Automatic Stop-Loss Exit"
            )
            
            if sell_result.get("success"):
                alerts.append({
                    "ticker": ticker,
                    "type": "STOP_LOSS_BREACH",
                    "title": f"CRITICAL: Auto-Exit {ticker}",
                    "message": f"Asset value dropped below safety threshold of ${stop_loss_val:.2f}. Sold at market price of ${latest_price:.2f}.",
                    "timestamp": sell_result["trade"]["timestamp"],
                    "details": sell_result["trade"]
                })
                
    return alerts

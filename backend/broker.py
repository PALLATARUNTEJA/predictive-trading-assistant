import os
import json
import time
from datetime import datetime

PORTFOLIO_FILE = os.path.join(os.path.dirname(__file__), "portfolio.json")

DEFAULT_PORTFOLIO = {
    "cash": 10000.0,
    "holdings": {},  # Format: "AAPL": {"shares": 10, "buy_price": 170.0, "stop_loss_pct": 20.0, "stop_loss_val": 136.0}
    "trade_log": [],
    "daily_start_value": 10000.0,
    "last_reset_date": "",
    "drawdown_limit_pct": 5.0  # Persistent user custom drawdown limit threshold
}

# Risk Management Settings
MAX_POSITION_SIZE_PCT = 0.20  # Max 20% of portfolio cash can be put in a single trade
IS_TRADING_FROZEN = False

def load_portfolio() -> dict:
    """
    Loads portfolio data from local JSON database. Initializes if doesn't exist.
    """
    if not os.path.exists(PORTFOLIO_FILE):
        save_portfolio(DEFAULT_PORTFOLIO)
        return DEFAULT_PORTFOLIO
    try:
        with open(PORTFOLIO_FILE, "r") as f:
            data = json.load(f)
            # Make sure all keys exist
            for k, v in DEFAULT_PORTFOLIO.items():
                if k not in data:
                    data[k] = v
            return data
    except Exception as e:
        print(f"Error loading portfolio JSON: {e}")
        return DEFAULT_PORTFOLIO

def save_portfolio(data: dict):
    """
    Saves portfolio data back to local JSON file.
    """
    try:
        with open(PORTFOLIO_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error saving portfolio JSON: {e}")

def check_drawdown_limit(portfolio: dict, current_total_value: float) -> bool:
    """
    Checks if daily drawdown limit has been breached.
    """
    global IS_TRADING_FROZEN
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # Check if we need to reset the daily starting value
    if portfolio.get("last_reset_date") != today_str:
        portfolio["daily_start_value"] = current_total_value
        portfolio["last_reset_date"] = today_str
        save_portfolio(portfolio)
        
    start_value = portfolio["daily_start_value"]
    drawdown = (start_value - current_total_value) / start_value
    
    drawdown_limit = portfolio.get("drawdown_limit_pct", 5.0) / 100.0
    if drawdown >= drawdown_limit:
        IS_TRADING_FROZEN = True
        return True
    
    IS_TRADING_FROZEN = False
    return False

def get_portfolio_status(current_prices: dict = None) -> dict:
    """
    Calculates current portfolio value, returns holdings with profits, and logs.
    """
    portfolio = load_portfolio()
    holdings = portfolio["holdings"]
    total_holdings_value = 0.0
    
    detailed_holdings = {}
    for ticker, h in holdings.items():
        # Get latest price, fallback to purchase price
        cur_price = current_prices.get(ticker, h["buy_price"]) if current_prices else h["buy_price"]
        value = h["shares"] * cur_price
        total_holdings_value += value
        
        profit = (cur_price - h["buy_price"]) * h["shares"]
        profit_pct = ((cur_price - h["buy_price"]) / h["buy_price"]) * 100 if h["buy_price"] > 0 else 0.0
        
        detailed_holdings[ticker] = {
            "shares": h["shares"],
            "buy_price": h["buy_price"],
            "current_price": cur_price,
            "value": value,
            "stop_loss_pct": h["stop_loss_pct"],
            "stop_loss_val": h["stop_loss_val"],
            "profit": profit,
            "profit_pct": profit_pct
        }
        
    total_val = portfolio["cash"] + total_holdings_value
    drawdown_breached = check_drawdown_limit(portfolio, total_val)
    
    # Calculate cumulative portfolio P/L (Total value vs starting $10,000 cash or reset amount)
    # For a simple local dashboard, P/L compares against the start of daily value or initial $10k
    starting_investment = 10000.0
    total_profit = total_val - starting_investment
    total_profit_pct = (total_profit / starting_investment) * 100
    
    return {
        "cash": portfolio["cash"],
        "total_value": total_val,
        "holdings_value": total_holdings_value,
        "holdings": detailed_holdings,
        "trade_log": portfolio["trade_log"][-20:],  # Return last 20 trades
        "drawdown_breached": drawdown_breached,
        "trading_frozen": IS_TRADING_FROZEN,
        "daily_start_value": portfolio["daily_start_value"],
        "drawdown_limit_pct": portfolio.get("drawdown_limit_pct", 5.0),
        "total_profit": total_profit,
        "total_profit_pct": total_profit_pct
    }

def buy_stock(ticker: str, price: float, cash_amount: float, stop_loss_pct: float = 20.0) -> dict:
    """
    Executes a virtual buy order with safety limits (drawdown check & position limit check).
    """
    portfolio = load_portfolio()
    status = get_portfolio_status()
    
    # 1. Check if trading is frozen due to drawdown limits
    if status["trading_frozen"]:
        return {"success": False, "reason": "Trading is frozen due to Daily Drawdown Limit breach."}
        
    # 2. Check cash availability
    if cash_amount > portfolio["cash"]:
        return {"success": False, "reason": f"Insufficient cash. Available: ${portfolio['cash']:.2f}, Requested: ${cash_amount:.2f}."}
        
    # 3. Check position size limit (Max 20% of total portfolio value)
    total_portfolio_value = status["total_value"]
    max_allowed_position = total_portfolio_value * MAX_POSITION_SIZE_PCT
    if cash_amount > max_allowed_position:
        return {
            "success": False, 
            "reason": f"Position size too large. Max position size allowed is 20% of portfolio (${max_allowed_position:.2f})."
        }
        
    # Calculate shares to buy
    shares = cash_amount / price
    if shares <= 0:
        return {"success": False, "reason": "Invalid transaction size."}
        
    # Calculate stop loss price
    stop_loss_val = price * (1 - (stop_loss_pct / 100.0))
    
    # Update portfolio
    portfolio["cash"] -= cash_amount
    holdings = portfolio["holdings"]
    
    if ticker in holdings:
        # Average down / purchase additional shares
        total_shares = holdings[ticker]["shares"] + shares
        total_cost = (holdings[ticker]["shares"] * holdings[ticker]["buy_price"]) + cash_amount
        avg_price = total_cost / total_shares
        
        holdings[ticker]["shares"] = total_shares
        holdings[ticker]["buy_price"] = avg_price
        # Maintain user-specified stop loss pct relative to the average purchase price
        holdings[ticker]["stop_loss_val"] = avg_price * (1 - (holdings[ticker]["stop_loss_pct"] / 100.0))
    else:
        holdings[ticker] = {
            "shares": shares,
            "buy_price": price,
            "stop_loss_pct": stop_loss_pct,
            "stop_loss_val": stop_loss_val
        }
        
    # Log trade
    trade_log = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "type": "BUY",
        "ticker": ticker,
        "shares": shares,
        "price": price,
        "total_amount": cash_amount,
        "reason": "Manual Order",
        "stop_loss": stop_loss_val
    }
    portfolio["trade_log"].append(trade_log)
    save_portfolio(portfolio)
    
    return {"success": True, "trade": trade_log}

def sell_stock(ticker: str, price: float, shares_to_sell: float = None, reason: str = "Manual Order") -> dict:
    """
    Executes a virtual sell order supporting partial sales.
    """
    portfolio = load_portfolio()
    holdings = portfolio["holdings"]
    
    if ticker not in holdings:
        return {"success": False, "reason": f"No holdings found for {ticker}."}
        
    holding = holdings[ticker]
    available_shares = holding["shares"]
    
    # If no shares specified or specified more than available, sell everything
    if shares_to_sell is None or shares_to_sell >= available_shares or abs(shares_to_sell - available_shares) < 1e-5:
        shares_to_sell = available_shares
        
    revenue = shares_to_sell * price
    
    # Update holdings
    if abs(shares_to_sell - available_shares) < 1e-5:
        del holdings[ticker]
    else:
        holding["shares"] -= shares_to_sell
        
    portfolio["cash"] += revenue
    
    # Log trade
    trade_log = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "type": "SELL",
        "ticker": ticker,
        "shares": shares_to_sell,
        "price": price,
        "total_amount": revenue,
        "reason": reason
    }
    portfolio["trade_log"].append(trade_log)
    save_portfolio(portfolio)
    
    return {"success": True, "trade": trade_log}

def update_drawdown_settings(limit_pct: float) -> dict:
    """
    Saves a custom drawdown limit threshold to portfolio.json.
    """
    portfolio = load_portfolio()
    portfolio["drawdown_limit_pct"] = limit_pct
    save_portfolio(portfolio)
    return {"success": True, "drawdown_limit_pct": limit_pct}

def reset_portfolio():
    """
    Resets portfolio ledger to default state.
    """
    save_portfolio(DEFAULT_PORTFOLIO)
    global IS_TRADING_FROZEN
    IS_TRADING_FROZEN = False
    return DEFAULT_PORTFOLIO

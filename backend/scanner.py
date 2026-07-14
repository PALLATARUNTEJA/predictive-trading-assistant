import pandas as pd
import numpy as np
import yfinance as yf

def fetch_data(ticker: str, period: str = "60d", interval: str = "1d") -> pd.DataFrame:
    """
    Fetches historical data for a given ticker from Yahoo Finance.
    """
    try:
        # Fetch data. Force it to be a DataFrame
        df = yf.download(ticker, period=period, interval=interval, progress=False)
        if df.empty:
            return pd.DataFrame()
        # Flatten MultiIndex columns if present (common in yfinance v0.2.x+)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]
        return df
    except Exception as e:
        print(f"Error fetching data for {ticker}: {e}")
        return pd.DataFrame()

def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates technical indicators on the historical dataframe.
    Calculates: SMA_20, SMA_50, RSI_14, MACD, Bollinger Bands, ATR.
    """
    if df.empty or len(df) < 50:
        return df

    # Close price series
    close = df['Close']

    # 1. Simple Moving Averages
    df['SMA_20'] = close.rolling(window=20).mean()
    df['SMA_50'] = close.rolling(window=50).mean()

    # 2. Relative Strength Index (RSI)
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-9)
    df['RSI_14'] = 100 - (100 / (1 + rs))

    # 3. MACD (12, 26, 9)
    exp1 = close.ewm(span=12, adjust=False).mean()
    exp2 = close.ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']

    # 4. Bollinger Bands (20, 2)
    df['BB_Mid'] = df['SMA_20']
    rstd = close.rolling(window=20).std()
    df['BB_High'] = df['BB_Mid'] + (rstd * 2)
    df['BB_Low'] = df['BB_Mid'] - (rstd * 2)

    # 5. Average True Range (ATR_14)
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - close.shift())
    low_close = np.abs(df['Low'] - close.shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    df['ATR_14'] = true_range.rolling(window=14).mean()

    # Fill NaNs with backfill/forwardfill to avoid training issues
    df = df.bfill().ffill()
    return df

def detect_patterns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detects basic candlestick patterns and spikes:
    - Hammer (bullish reversal)
    - Shooting Star (bearish reversal)
    - Bullish Engulfing
    - Bearish Engulfing
    - Price Spike (change > 2.5 std dev)
    - Volume Spike (volume > 2 * average volume)
    """
    if df.empty or len(df) < 5:
        df['Pattern'] = 'None'
        df['Spike'] = 'None'
        return df

    patterns = []
    spikes = []

    # Calculate average volume and daily return standard deviation for spikes
    avg_vol = df['Volume'].rolling(window=20).mean()
    std_vol = df['Volume'].rolling(window=20).std()
    returns = df['Close'].pct_change()
    std_returns = returns.rolling(window=20).std()

    for i in range(len(df)):
        if i < 2:
            patterns.append('None')
            spikes.append('None')
            continue

        row = df.iloc[i]
        prev_row = df.iloc[i-1]
        
        # Candles body and shadow size
        open_val = float(row['Open'])
        close_val = float(row['Close'])
        high_val = float(row['High'])
        low_val = float(row['Low'])
        
        body = abs(close_val - open_val)
        candle_range = high_val - low_val if (high_val - low_val) > 0 else 1e-9
        
        # Upper/lower shadows
        lower_shadow = min(open_val, close_val) - low_val
        upper_shadow = high_val - max(open_val, close_val)
        
        pattern = 'None'
        # 1. Hammer (body in upper third, long lower shadow)
        if lower_shadow > (2 * body) and upper_shadow < (0.2 * candle_range) and body > 0:
            pattern = 'Bullish Hammer'
        # 2. Shooting Star (body in lower third, long upper shadow)
        elif upper_shadow > (2 * body) and lower_shadow < (0.2 * candle_range) and body > 0:
            pattern = 'Shooting Star'
        # 3. Engulfing patterns
        else:
            prev_open, prev_close = float(prev_row['Open']), float(prev_row['Close'])
            prev_body = abs(prev_close - prev_open)
            
            # Bullish Engulfing: previous red candle, current green candle fully engulfs it
            if prev_close < prev_open and close_val > open_val and open_val <= prev_close and close_val >= prev_open:
                pattern = 'Bullish Engulfing'
            # Bearish Engulfing: previous green candle, current red candle fully engulfs it
            elif prev_close > prev_open and close_val < open_val and open_val >= prev_close and close_val <= prev_open:
                pattern = 'Bearish Engulfing'

        patterns.append(pattern)

        # Spike detection
        spike = 'None'
        curr_return = returns.iloc[i]
        curr_vol = row['Volume']
        
        # Price spikes
        if pd.notna(curr_return) and pd.notna(std_returns.iloc[i]) and abs(curr_return) > (2.5 * std_returns.iloc[i]):
            spike = 'Price Spike Up' if curr_return > 0 else 'Price Spike Down'
        # Volume spikes
        elif pd.notna(curr_vol) and pd.notna(avg_vol.iloc[i]) and pd.notna(std_vol.iloc[i]) and curr_vol > (avg_vol.iloc[i] + 2 * std_vol.iloc[i]):
            spike = 'Volume Spike'

        spikes.append(spike)

    df['Pattern'] = patterns
    df['Spike'] = spikes
    return df

def get_market_analysis(ticker: str) -> dict:
    """
    Combines fetching, indicator calculations, pattern detection, and return summary statistics.
    """
    df = fetch_data(ticker)
    if df.empty:
        return {}
    
    df = calculate_indicators(df)
    df = detect_patterns(df)
    
    latest = df.iloc[-1]
    
    # Simple rule-based trend explanation
    trend = "Neutral"
    if float(latest['Close']) > float(latest['SMA_20']) and float(latest['SMA_20']) > float(latest['SMA_50']):
        trend = "Bullish"
    elif float(latest['Close']) < float(latest['SMA_20']) and float(latest['SMA_20']) < float(latest['SMA_50']):
        trend = "Bearish"
        
    return {
        "ticker": ticker,
        "price": float(latest['Close']),
        "change": float(((latest['Close'] - df.iloc[-2]['Close']) / df.iloc[-2]['Close']) * 100) if len(df) > 1 else 0.0,
        "rsi": float(latest['RSI_14']),
        "macd": float(latest['MACD']),
        "macd_signal": float(latest['MACD_Signal']),
        "bb_high": float(latest['BB_High']),
        "bb_low": float(latest['BB_Low']),
        "atr": float(latest['ATR_14']),
        "trend": trend,
        "pattern": latest['Pattern'],
        "spike": latest['Spike'],
        "volume": int(latest['Volume'])
    }

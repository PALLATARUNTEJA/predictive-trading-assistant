import os
import joblib
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
from backend.scanner import fetch_data, calculate_indicators, detect_patterns

MODEL_PATH = os.path.join(os.path.dirname(__file__), "model.joblib")

def prepare_features(df: pd.DataFrame, prediction_horizon: int = 3) -> tuple:
    """
    Extracts features for machine learning and creates target labels.
    Features:
    - Close / SMA_20 ratio
    - Close / SMA_50 ratio
    - SMA_20 / SMA_50 ratio
    - RSI_14
    - MACD normalized (MACD / Close)
    - MACD_Hist normalized (MACD_Hist / Close)
    - BB Bandwidth ((BB_High - BB_Low) / BB_Mid)
    - Bollinger %B ((Close - BB_Low) / (BB_High - BB_Low + 1e-9))
    - ATR normalized (ATR_14 / Close)
    """
    if df.empty or len(df) < 50:
        return pd.DataFrame(), pd.Series()

    # Calculate indicators if not already present
    if 'SMA_20' not in df.columns:
        df = calculate_indicators(df)

    close = df['Close']

    # Feature Engineering
    features = pd.DataFrame(index=df.index)
    features['Close_SMA20'] = close / df['SMA_20']
    features['Close_SMA50'] = close / df['SMA_50']
    features['SMA20_SMA50'] = df['SMA_20'] / df['SMA_50']
    features['RSI'] = df['RSI_14']
    features['MACD_Norm'] = df['MACD'] / close
    features['MACD_Hist_Norm'] = df['MACD_Hist'] / close
    features['BB_Bandwidth'] = (df['BB_High'] - df['BB_Low']) / df['BB_Mid']
    features['BB_pctB'] = (close - df['BB_Low']) / (df['BB_High'] - df['BB_Low'] + 1e-9)
    features['ATR_Norm'] = df['ATR_14'] / close

    # Target: 1 if price rises in `prediction_horizon` days, 0 otherwise
    # shift(-prediction_horizon) shifts the future close price back to today's row
    future_close = close.shift(-prediction_horizon)
    target = (future_close > close).astype(int)

    # Align features and target (drop last prediction_horizon rows where target is NaN)
    valid_idx = target.dropna().index
    X = features.loc[valid_idx]
    y = target.loc[valid_idx]

    return X, y

def train_model(tickers: list = None) -> dict:
    """
    Fetches historical data, trains a RandomForestClassifier, and saves the model.
    """
    if not tickers:
        # Default representative stocks
        tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "JPM", "V", "DIS"]

    all_X = []
    all_y = []

    print("Fetching training data for tickers:", tickers)
    for ticker in tickers:
        df = fetch_data(ticker, period="max", interval="1d")
        if df.empty or len(df) < 100:
            continue
        X_t, y_t = prepare_features(df)
        if not X_t.empty:
            all_X.append(X_t)
            all_y.append(y_t)

    if not all_X:
        return {"success": False, "error": "No sufficient training data fetched."}

    X = pd.concat(all_X, axis=0)
    y = pd.concat(all_y, axis=0)

    # Train-test split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Initialize model
    model = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42)
    model.fit(X_train, y_train)

    # Evaluate model
    train_acc = accuracy_score(y_train, model.predict(X_train))
    test_acc = accuracy_score(y_test, model.predict(X_test))

    print(f"Model trained. Train Acc: {train_acc:.2%}, Test Acc: {test_acc:.2%}")

    # Save model
    joblib.dump(model, MODEL_PATH)

    return {
        "success": True,
        "train_accuracy": float(train_acc),
        "test_accuracy": float(test_acc),
        "samples_trained": int(len(X))
    }

def get_prediction(ticker: str) -> dict:
    """
    Loads model, prepares the latest single row of features, and returns prediction.
    If the model doesn't exist, trains a new one.
    """
    if not os.path.exists(MODEL_PATH):
        print("Model file not found. Training new model...")
        train_result = train_model()
        if not train_result.get("success"):
            return {"prediction": "Unknown", "confidence": 0.0, "reason": "Failed to train model."}

    try:
        model = joblib.load(MODEL_PATH)
    except Exception as e:
        print(f"Error loading model: {e}")
        return {"prediction": "Unknown", "confidence": 0.0, "reason": "Failed to load model."}

    # Fetch latest data
    df = fetch_data(ticker, period="60d", interval="1d")
    if df.empty or len(df) < 50:
        return {"prediction": "Unknown", "confidence": 0.0, "reason": "Insufficient historical data."}

    # Prepare features for the latest date (the last row)
    X_t, _ = prepare_features(df)
    if X_t.empty:
        return {"prediction": "Unknown", "confidence": 0.0, "reason": "Feature engineering failed."}

    # We predict using the last row
    latest_features = X_t.iloc[[-1]]

    # Predict
    pred_class = model.predict(latest_features)[0]
    pred_prob = model.predict_proba(latest_features)[0]

    confidence = pred_prob[pred_class]
    prediction_label = "UP" if pred_class == 1 else "DOWN"

    return {
        "prediction": prediction_label,
        "confidence": float(confidence),
        "target_days": 3,
        "reason": f"Random Forest predict trend with {confidence:.1%} confidence."
    }

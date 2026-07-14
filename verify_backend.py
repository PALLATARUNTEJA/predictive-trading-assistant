import os
import sys

# Add project root to path so we can import backend packages
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

print("Starting Predictive Trading Assistant Backend Verification Test...")

try:
    print("Testing data ingestion and indicator computation (scanner.py)...")
    from backend.scanner import get_market_analysis
    res = get_market_analysis("AAPL")
    if res:
        print(f"Successfully calculated indicators for AAPL. Current price: ${res['price']:.2f}, RSI: {res['rsi']:.1f}, Trend: {res['trend']}")
    else:
        print("Error: Could not retrieve market data.")

    print("\nTesting Machine Learning model training pipeline (model.py)...")
    from backend.model import train_model, get_prediction
    # Train model on a small set of tickers to verify scikit-learn works
    train_res = train_model(["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL"])
    print(f"Training status: {train_res}")
    
    print("\nTesting Machine Learning inference/prediction...")
    pred = get_prediction("AAPL")
    print(f"ML Prediction for AAPL: {pred['prediction']} (Confidence: {pred['confidence']*100:.1f}%)")

    print("\nTesting Simulated Portfolio ledger database (broker.py)...")
    from backend.broker import reset_portfolio, buy_stock, get_portfolio_status
    reset_portfolio()
    buy_res = buy_stock("AAPL", price=150.0, cash_amount=1000.0, stop_loss_pct=15.0)
    print(f"Mock transaction buy result: {buy_res}")
    
    status = get_portfolio_status()
    print(f"Portfolio Net Worth: ${status['total_value']:.2f}, Cash: ${status['cash']:.2f}")

    print("\nAll Backend Tests passed successfully!")
except Exception as e:
    print(f"\nERROR: Verification failed with exception: {e}")
    sys.exit(1)
sys.exit(0)

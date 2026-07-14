# Predictive Trading Assistant 📈🤖

An enterprise-grade, local-first **Predictive Trading Assistant** designed to help retail investors scan the stock market, execute paper trades with strict risk filters, generate machine learning-based price forecasts, and enforce automated stop-loss exits.

Developed using **Python (FastAPI, Scikit-Learn, Pandas)** and a **modern, responsive Glassmorphism UI (HTML/CSS/JS)**.

---

## Key Features

1. **Local Machine Learning Forecasts**:
   - Uses a local **Random Forest Classifier** trained on historical technical indicators (RSI, MACD, Bollinger Bands, ATR, SMA) to predict price movements over a 3-day horizon.
   - Provides confidence percentages for predictions, eliminating paid third-party model dependency.
2. **Technical Indicator & Candlestick Pattern Scanner**:
   - Downloads real-time market data from **Yahoo Finance (100% Free, no keys required)**.
   - Detects candlestick reversal patterns (e.g. *Bullish Hammer*, *Shooting Star*, *Engulfing*) and standard-deviation-based price/volume spikes.
3. **Automated Exit & Debt Protection (Risk Management)**:
   - **Stop-Loss Execution**: Automatically executes simulated exit (SELL) orders if a stock value drops below a user-defined threshold (e.g. exiting when initial value drops below 80%).
   - **Daily Drawdown Cap**: Freezes trading activities for the day if net portfolio value drops by 5% or more from its starting value.
   - **Max Position Sizing**: Caps the capital allocated to any single stock at 20% of net value.
4. **Natural Language Trend Explainer**:
   - Translates complex mathematical indicators (MACD crossovers, overbought/oversold RSI levels, SMA cross-unders) into structured, readable English explanations.
5. **Interactive Glossary Guide**:
   - Built-in terminology panel to explain concepts like *Bullish*, *Bearish*, *MACD*, *RSI*, and *Hammer Reversals* to new users.

---

## Architecture & Project Structure

The project follows a clean separation-of-concerns architecture:

```
predictive_trading_assistant/
│
├── backend/
│   ├── app.py             # FastAPI REST endpoints & WebSocket server
│   ├── scanner.py         # Technical analysis engine & candlestick scanner
│   ├── model.py           # ML Random Forest training, saving, and inference
│   ├── broker.py          # Portfolio ledger, risk management, and Alpaca connectivity
│   ├── alerts.py          # Stop-loss monitoring background safety checker
│   └── portfolio.json     # Saved portfolio state database
│
├── frontend/
│   ├── index.html         # Glassmorphism UI layout
│   ├── styles.css         # Dark theme custom variables and animations
│   └── app.js             # TradingView chart drawing, API loaders, & Websockets
│
├── verify_backend.py      # Automated backend pipeline validation test
└── README.md              # Documentation
```

---

## Quick Start Guide

### 1. Prerequisite Installations
Ensure Python (3.9+) is installed. Open your terminal and install backend dependencies:
```bash
pip install yfinance pandas numpy scikit-learn joblib fastapi uvicorn pydantic
```

### 2. Verify the Backend Pipeline
Before starting the servers, run the automated integration test to verify data calculations, model training, and portfolio actions:
```bash
python verify_backend.py
```
*You should see `All Backend Tests passed successfully!` in your terminal.*

### 3. Launch the Backend API
Start the FastAPI server on port 8000:
```bash
python backend/app.py
```
*The server will reload automatically on file changes.*

### 4. Load the Dashboard UI
Simply double-click/open the [frontend/index.html](file:///C:/Users/JOBIAK/.gemini/antigravity/scratch/predictive_trading_assistant/frontend/index.html) file in Google Chrome, Microsoft Edge, or any modern web browser.

---

## Trading Integrations & Privacy
* **Simulation Mode**: By default, the application runs in a simulated sandbox environment (Mock Paper Trading) with virtual funds ($10,000 balance).
* **Broker Connection**: To connect to a live account, a developer-friendly Alpaca client adapter is provided in `backend/broker.py`. 
* **Secrets Storage**: Always place your keys (e.g. `ALPACA_API_KEY`) inside a local `.env` file. Do not commit key files to version control repositories.

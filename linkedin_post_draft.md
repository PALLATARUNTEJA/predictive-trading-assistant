# Friday AI - LinkedIn Promotion Strategy & Post Drafts

This guide contains strategies, screenshot recommendations, and multiple post drafts to help you present **Friday AI** on LinkedIn as a professional software engineering project.

---

## 📸 Recommended Screenshots to Capture

For the best visual appeal, capture these **4 high-resolution screenshot views** from your desktop browser:

1. **The Candlestick Chart View (`#view-chart`)**:
   * *What to show*: Load a highly active stock (like `NVDA` or `TSLA`). Hover your cursor over a candlestick so the crosshair displays the active Open/High/Low/Close details in the top legend, showing off the TradingView grid lines and the blue SMA overlays.
2. **The Real-Time Market Signals Scanner (`#view-signals`)**:
   * *What to show*: Click "Signals" on the floating dock. Show the expanded full-width table displaying the ML direction forecast column (e.g., "UP" or "DOWN"), confidence levels (e.g., "68%"), and the "Chart" action links.
3. **The Active Holdings Ledger (`#view-holdings`)**:
   * *What to show*: Show active ledger positions with the green profit indicators (e.g. `+$45.20`), stop-loss limits, and the partial share sell input box.
4. **The Chatbot Conversation Overlay**:
   * *What to show*: Type a question to Friday (like *"Analyze MSFT"* or *"What is my cash balance?"*) and capture the response bubble next to the floating bottom glassmorphism nav dock.

---

## 📝 LinkedIn Post Draft: Option 1 (Recommended - Developer Journey & Technical Focus)

*Copy and paste this draft. It emphasizes your learning journey, the software architecture, and the pre-trained ML capabilities:*

```text
🚀 I built an AI-Powered Predictive Trading Assistant & Portfolio Command Center: "Friday AI"

Over the past few weeks, I wanted to dive deep into building a real-time, interactive dashboard that merges quantitative data analysis with a premium, responsive UI. 

The result is Friday AI—a paper trading assistant that fetches stock market feeds, runs machine learning direction predictions, manages active portfolio drawdowns, and provides an NLP financial chatbot companion.

Here is what I implemented under the hood:

🧠 Machine Learning Direction Forecasts
Trained a Random Forest Classifier offline on over 41,000 historic daily candlestick rows (extracting RSI, MACD crossovers, and SMA ratios) to output short-term price trend forecasts and probability confidence ratings.

🛡️ Programmatic Risk & Capital Protection
Implemented an asynchronous safety check system in FastAPI. If an active position falls below its stop-loss threshold or if the overall portfolio drawdown breaches the user's slider setting, the server executes emergency liquidations and fires alerts.

⚡ Real-Time bi-directional WebSockets
Established a stateful WebSocket connection manager to push trade notifications and stop-loss alarms from the backend directly to the browser, triggering visual glows and warning chimes.

🎨 Creative UI & Canvas Rendering
- Interactive chart workspace powered by TradingView's Lightweight Charts.
- 3D WebGL particle space rendered using Three.js.
- Elastic mouse cursor trailing and view transitions using GSAP.
- Apple-style bottom floating navigation dock with glassmorphism styling.

🌐 Deployment
- Frontend: Hosted on GitHub Pages CDN for sub-second delivery.
- Backend: Deployed on Render serverless containers.

📖 As a developer resource, I've compiled a comprehensive 5-Chapter Project Handbook explaining the entire codebase line-by-line along with 50+ quantitative trading interview questions. I've attached the PDF report to this post!

Live Site: https://pallatarunteja.github.io/predictive-trading-assistant/
GitHub: https://github.com/PALLATARUNTEJA/predictive-trading-assistant

#Python #FastAPI #MachineLearning #DataScience #WebDevelopment #SoftwareEngineering #TradingView #GSAP #ThreeJS
```

---

## 📝 LinkedIn Post Draft: Option 2 (Concise & Feature-Oriented)

*Use this draft if you prefer a shorter post focusing strictly on product features:*

```text
🔥 Project Showcase: Building Friday AI - An Interactive ML Stock Assistant

I’m excited to share my latest project, Friday AI—a predictive trading assistant and real-time portfolio management dashboard.

What it does:
📈 Technical Indicator Charts: Fluid candles and SMA indicators rendered via TradingView Lightweight Charts canvas, fully synchronized to New York EST session hours.
🔮 ML Forecasts: Custom Random Forest classifier predicting 3-day direction targets on historic index datasets.
🚨 Asynchronous Alerts: Real-time WebSockets pushing emergency stop-loss exits and portfolio drawdown lockdowns.
💬 Chat Assistant: Multi-tiered NLP companion (routing between Gemini API, serverless Qwen LLM, and local SQLite data).
📱 Premium Design: Responsive, glassmorphic layout styled with Three.js WebGL backgrounds and GSAP physics.

Check out the code and handbook report below!

👉 Play live: https://pallatarunteja.github.io/predictive-trading-assistant/
👉 Code: https://github.com/PALLATARUNTEJA/predictive-trading-assistant

#FastAPI #Python #ScikitLearn #ThreeJS #WebSockets #QuantitativeTrading #PortfolioManagement
```

---

## ⚙️ How to Publish on LinkedIn for Maximum Engagement

To make the post look like a professional research report (which ranks higher in the LinkedIn algorithm):

1. **Generate the PDF**:
   * Open [project_comprehensive_handbook.html](file:///C:/Users/JOBIAK/.gemini/antigravity/scratch/predictive_trading_assistant/project_comprehensive_handbook.html) in your browser.
   * Press `Ctrl + P`, select **"Save as PDF"**, turn on **"Background graphics"**, and save the file as `Friday_AI_Developer_Handbook.pdf`.
2. **Create the LinkedIn Post**:
   * Click **"Start a post"** on your LinkedIn homepage.
   * Paste your chosen post text draft from above.
3. **Attach the PDF**:
   * Click the **"Add document"** icon (it looks like a sheet of paper).
   * Upload `Friday_AI_Developer_Handbook.pdf`.
   * Title it: **"Friday AI - Technical Architecture & Developer Handbook"**.
   * *Why this works*: LinkedIn turns PDF documents into an interactive, swipeable slideshow right inside your feed, allowing recruiters and developers to read your code explanations directly!
4. **Attach Screenshots in comments or as images**:
   * You can add the screenshots directly below the text, or upload them as a carousel image gallery.

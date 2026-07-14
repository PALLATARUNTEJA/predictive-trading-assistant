const API_BASE = (window.location.protocol === "file:") ? "http://127.0.0.1:8000" : "https://predictive-trading-assistant.onrender.com";
let activeTicker = "AAPL";
let activeInterval = "1d";
let activePeriod = "60d";
let tickInterval = null;
let latestOHLC = null; // Store latest candle data for tooltips
let chart = null;
let candleSeries = null;
let sma20Series = null;
let sma50Series = null;
let socket = null;

// Technical Chart Drawing Tools state
let activeTool = null; // Can be 'support', 'resistance', or null
let customPriceLines = []; // Store drawn price lines so we can clear them

// On document load
document.addEventListener("DOMContentLoaded", () => {
    initChart();
    initWebSocket();
    refreshPortfolio();
    loadTickerData(activeTicker);
    scanMarket();

    // Bind Event Listeners
    document.getElementById("btn-load-chart").addEventListener("click", () => {
        const input = document.getElementById("input-search-ticker").value.trim().toUpperCase();
        if (input) loadTickerData(input);
    });

    document.getElementById("input-search-ticker").addEventListener("keypress", (e) => {
        if (e.key === "Enter") {
            const input = document.getElementById("input-search-ticker").value.trim().toUpperCase();
            if (input) loadTickerData(input);
        }
    });

    document.getElementById("btn-scan-all").addEventListener("click", scanMarket);
    document.getElementById("btn-order-buy").addEventListener("click", executeBuy);
    document.getElementById("btn-reset").addEventListener("click", resetAccount);

    // Risk Settings Drawdown Slider
    const slider = document.getElementById("slider-drawdown");
    const lbl = document.getElementById("lbl-drawdown-threshold");
    
    slider.addEventListener("input", (e) => {
        lbl.innerText = `${parseFloat(e.target.value).toFixed(1)}%`;
    });

    slider.addEventListener("change", async (e) => {
        const val = parseFloat(e.target.value);
        await updateDrawdownSettings(val);
    });

    // Technical Chart Drawing Tools
    const btnSupport = document.getElementById("btn-tool-support");
    const btnResistance = document.getElementById("btn-tool-resistance");
    const btnClear = document.getElementById("btn-tool-clear");

    btnSupport.addEventListener("click", () => {
        activeTool = (activeTool === 'support') ? null : 'support';
        updateToolUI();
    });

    btnResistance.addEventListener("click", () => {
        activeTool = (activeTool === 'resistance') ? null : 'resistance';
        updateToolUI();
    });

    btnClear.addEventListener("click", () => {
        // Clear all drawn lines
        customPriceLines.forEach(line => {
            if (candleSeries) {
                try {
                    candleSeries.removePriceLine(line);
                } catch (e) {
                    console.error("Error removing line:", e);
                }
            }
        });
        customPriceLines = [];
        activeTool = null;
        updateToolUI();
    });

    // Glossary Modal
    const glossaryModal = document.getElementById("glossary-modal");
    document.getElementById("btn-glossary").addEventListener("click", () => {
        glossaryModal.classList.remove("hidden");
    });
    document.getElementById("btn-close-glossary").addEventListener("click", () => {
        glossaryModal.classList.add("hidden");
    });
    document.getElementById("btn-close-glossary-bottom").addEventListener("click", () => {
        glossaryModal.classList.add("hidden");
    });
    glossaryModal.addEventListener("click", (e) => {
        if (e.target === glossaryModal) glossaryModal.classList.add("hidden");
    });

    // Timeframe selector buttons
    const tfButtons = document.querySelectorAll(".btn-tf");
    tfButtons.forEach(btn => {
        btn.addEventListener("click", (e) => {
            tfButtons.forEach(b => b.classList.remove("active"));
            e.currentTarget.classList.add("active");
            activeInterval = e.currentTarget.getAttribute("data-interval");
            activePeriod = e.currentTarget.getAttribute("data-period");
            loadTickerData(activeTicker);
        });
    });
});

// Helper to update tool button styling state
function updateToolUI() {
    const btnSupport = document.getElementById("btn-tool-support");
    const btnResistance = document.getElementById("btn-tool-resistance");

    btnSupport.className = activeTool === 'support' ? "btn btn-tool active" : "btn btn-tool";
    btnResistance.className = activeTool === 'resistance' ? "btn btn-tool active" : "btn btn-tool";
}

// Initialize TradingView Chart
function initChart() {
    const container = document.getElementById("tradingview-chart");
    container.innerHTML = "";

    chart = LightweightCharts.createChart(container, {
        layout: {
            background: { type: 'solid', color: '#0a0d14' },
            textColor: '#94a3b8',
            fontFamily: 'Inter, sans-serif'
        },
        grid: {
            vertLines: { color: 'rgba(255, 255, 255, 0.02)' },
            horzLines: { color: 'rgba(255, 255, 255, 0.02)' },
        },
        rightPriceScale: {
            borderColor: 'rgba(255, 255, 255, 0.08)',
        },
        timeScale: {
            borderColor: 'rgba(255, 255, 255, 0.08)',
            timeVisible: true,
            secondsVisible: false,
            // Format ticks on X-axis dynamically to New York Exchange Time
            tickMarkFormatter: (time, tickMarkType, locale) => {
                if (typeof time === 'number') {
                    const date = new Date(time * 1000);
                    return date.toLocaleTimeString('en-US', {
                        hour: '2-digit',
                        minute: '2-digit',
                        hour12: false,
                        timeZone: 'America/New_York'
                    });
                }
                return time;
            }
        },
        localization: {
            // Format time on crosshair tooltip to New York Exchange Time
            timeFormatter: (time) => {
                if (typeof time === 'number') {
                    const date = new Date(time * 1000);
                    return date.toLocaleString('en-US', {
                        year: 'numeric',
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                        hour12: false,
                        timeZone: 'America/New_York'
                    }) + ' (EST)';
                }
                return time;
            }
        },
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
        },
    });

    candleSeries = chart.addCandlestickSeries({
        upColor: '#4ade80',
        downColor: '#f87171',
        borderDownColor: '#f87171',
        borderUpColor: '#4ade80',
        wickDownColor: '#f87171',
        wickUpColor: '#4ade80',
    });

    sma20Series = chart.addLineSeries({
        color: '#00f3ff',
        lineWidth: 1.5,
        title: 'SMA 20'
    });

    sma50Series = chart.addLineSeries({
        color: '#3b82f6',
        lineWidth: 1.5,
        title: 'SMA 50'
    });

    // Subscribe to clicks to draw Custom Support / Resistance levels
    chart.subscribeClick((param) => {
        if (!param || !param.price || !candleSeries || !activeTool) return;

        // Fetch price of selected coordinate
        const price = param.price;
        const color = activeTool === 'support' ? '#4ade80' : '#f87171';
        const label = activeTool === 'support' ? 'Support Level' : 'Resistance Level';
        
        // Draw the line
        const line = candleSeries.createPriceLine({
            price: price,
            color: color,
            lineWidth: 1.5,
            lineStyle: LightweightCharts.LineStyle.Dashed,
            axisLabelVisible: true,
            title: label,
        });

        customPriceLines.push(line);
        activeTool = null; // Reset tool selection
        updateToolUI();
    });

    // Subscribe to crosshair move to show OHLC values in header
    chart.subscribeCrosshairMove((param) => {
        const ohlcLegend = document.getElementById("ohlc-legend");
        if (!ohlcLegend) return;

        let o = "-", h = "-", l = "-", c = "-";

        if (param && param.point && param.seriesPrices) {
            const priceObj = param.seriesPrices.get(candleSeries);
            if (priceObj) {
                o = `$${priceObj.open.toFixed(2)}`;
                h = `$${priceObj.high.toFixed(2)}`;
                l = `$${priceObj.low.toFixed(2)}`;
                c = `$${priceObj.close.toFixed(2)}`;
            }
        } else if (latestOHLC) {
            // Default to latest loaded candle when not hovering
            o = `$${latestOHLC.open.toFixed(2)}`;
            h = `$${latestOHLC.high.toFixed(2)}`;
            l = `$${latestOHLC.low.toFixed(2)}`;
            c = `$${latestOHLC.close.toFixed(2)}`;
        }

        document.getElementById("ohlc-o").innerText = o;
        document.getElementById("ohlc-h").innerText = h;
        document.getElementById("ohlc-l").innerText = l;
        document.getElementById("ohlc-c").innerText = c;
    });

    window.addEventListener("resize", () => {
        if (chart) {
            chart.resize(container.clientWidth, container.clientHeight);
        }
    });
}

// Initialize WebSockets
function initWebSocket() {
    let wsHost = window.location.host;
    if (window.location.protocol === "file:") {
        wsHost = "127.0.0.1:8000";
    }
    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${wsProtocol}//${wsHost}/ws`;
    socket = new WebSocket(wsUrl);

    socket.onopen = () => {
        document.getElementById("ws-status-dot").className = "pulse-dot green";
        document.getElementById("ws-status-text").innerText = "Live Connected";
    };

    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleLiveNotification(data);
    };

    socket.onclose = () => {
        document.getElementById("ws-status-dot").className = "pulse-dot red";
        document.getElementById("ws-status-text").innerText = "Disconnected. Retrying...";
        setTimeout(initWebSocket, 3000);
    };
}

// Process Real-time alert notifications
function handleLiveNotification(data) {
    const alertsContainer = document.getElementById("alerts-container");
    const item = document.createElement("div");
    
    const now = new Date();
    const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    
    if (data.type === "STOP_LOSS_BREACH") {
        item.className = "alert-item danger";
        item.innerHTML = `
            <span class="alert-time">${timeStr}</span>
            <div class="alert-content">
                <strong class="text-red">${data.title}</strong>
                <p>${data.message}</p>
            </div>
        `;
        playChime('danger');
        
        // Glow card frame briefly
        document.body.classList.add("danger-glow");
        setTimeout(() => document.body.classList.remove("danger-glow"), 3000);
        
        refreshPortfolio();
    } else if (data.type === "TRADE") {
        item.className = "alert-item trade";
        item.innerHTML = `
            <span class="alert-time">${timeStr}</span>
            <div class="alert-content">
                <strong class="text-green">${data.title}</strong>
                <p>${data.message}</p>
            </div>
        `;
        playChime('success');
        refreshPortfolio();
    } else {
        item.className = "alert-item system";
        item.innerHTML = `
            <span class="alert-time">${timeStr}</span>
            <div class="alert-content">
                <strong>${data.title || "Notification"}</strong>
                <p>${data.message}</p>
            </div>
        `;
    }

    alertsContainer.prepend(item);
}

// Load Stock Candlestick Data
async function loadTickerData(ticker) {
    activeTicker = ticker;
    document.getElementById("chart-loader").classList.remove("hidden");
    document.getElementById("order-ticker").value = ticker;

    try {
        const response = await fetch(`${API_BASE}/api/chart/${ticker}?interval=${activeInterval}&period=${activePeriod}`);
        if (!response.ok) throw new Error("Ticker search failed.");
        const data = await response.json();
        
        if (data.length > 0) {
            const candles = data.map(d => ({
                time: d.time,
                open: d.open,
                high: d.high,
                low: d.low,
                close: d.close
            }));
            
            const sma20 = data.filter(d => d.sma_20 !== null).map(d => ({
                time: d.time,
                value: d.sma_20
            }));

            const sma50 = data.filter(d => d.sma_50 !== null).map(d => ({
                time: d.time,
                value: d.sma_50
            }));

            candleSeries.setData(candles);
            sma20Series.setData(sma20);
            sma50Series.setData(sma50);
            
            chart.timeScale().fitContent();

            const latest = data[data.length - 1];
            const prev = data[data.length - 2] || latest;
            const price = latest.close;
            const change = ((price - prev.close) / prev.close) * 100;
            
            document.getElementById("chart-ticker-name").innerText = ticker;
            document.getElementById("chart-ticker-price").innerText = `$${price.toFixed(2)}`;
            
            const changeText = document.getElementById("chart-ticker-change");
            changeText.innerText = `${change >= 0 ? '+' : ''}${change.toFixed(2)}%`;
            changeText.className = change >= 0 ? "text-green" : "text-red";

            latestOHLC = latest;
            
            // Set initial legend OHLC values
            document.getElementById("ohlc-o").innerText = `$${latest.open.toFixed(2)}`;
            document.getElementById("ohlc-h").innerText = `$${latest.high.toFixed(2)}`;
            document.getElementById("ohlc-l").innerText = `$${latest.low.toFixed(2)}`;
            document.getElementById("ohlc-c").innerText = `$${latest.close.toFixed(2)}`;
        }

        // Fetch recommendations & explainer markdown
        fetchAIAnalysis(ticker);

        // Start live ticking background polling
        if (tickInterval) clearInterval(tickInterval);
        tickInterval = setInterval(async () => {
            if (document.hidden) return;
            await fetchLatestPriceTick(ticker);
        }, 5000);

    } catch (err) {
        console.error(err);
        alert(`Error loading data for ${ticker}: ${err.message}`);
    } finally {
        document.getElementById("chart-loader").classList.add("hidden");
    }
}

async function fetchLatestPriceTick(ticker) {
    try {
        const res = await fetch(`${API_BASE}/api/tick/${ticker}?interval=${activeInterval}`);
        if (!res.ok) return;
        const tick = await res.json();
        
        if (candleSeries) {
            candleSeries.update({
                time: tick.time,
                open: tick.open,
                high: tick.high,
                low: tick.low,
                close: tick.close
            });
            
            document.getElementById("chart-ticker-price").innerText = `$${tick.close.toFixed(2)}`;
            latestOHLC = tick;
            
            // Update legend OHLC values in real-time
            document.getElementById("ohlc-o").innerText = `$${tick.open.toFixed(2)}`;
            document.getElementById("ohlc-h").innerText = `$${tick.high.toFixed(2)}`;
            document.getElementById("ohlc-l").innerText = `$${tick.low.toFixed(2)}`;
            document.getElementById("ohlc-c").innerText = `$${tick.close.toFixed(2)}`;
        }
    } catch (e) {
        console.error("Price ticking fetch error:", e);
    }
}

// Fetch predictions & risk analysis
async function fetchAIAnalysis(ticker) {
    try {
        // Scikit-Learn Prediction
        const scanRes = await fetch(`${API_BASE}/api/scan?tickers=${ticker}`);
        if (scanRes.ok) {
            const list = await scanRes.json();
            if (list.length > 0) {
                const ai = list[0];
                const isUp = ai.prediction === "UP";
                
                const predEl = document.getElementById("ai-prediction");
                predEl.innerText = ai.prediction;
                predEl.className = isUp ? "ai-pred-val text-green" : "ai-pred-val text-red";

                const bar = document.getElementById("ai-confidence-bar");
                bar.className = isUp ? "progress-bar-fill green" : "progress-bar-fill red";
                bar.style.width = `${ai.confidence * 100}%`;

                document.getElementById("ai-confidence-text").innerText = `${(ai.confidence * 100).toFixed(1)}% Conf.`;

                // Update Dynamic Stop Loss Suggestions based on standard deviation / ATR Volatility
                const atrPct = (ai.atr / ai.price) * 100;
                let recommendedStop = (atrPct * 1.8).toFixed(1);
                if (recommendedStop < 3.0) recommendedStop = 5.0; // Hard limit tight stops
                
                const suggestionEl = document.getElementById("ai-risk-suggestion");
                if (atrPct > 4.5) {
                    suggestionEl.innerHTML = `
                        <i class="fa-solid fa-circle-exclamation text-yellow"></i>
                        <span>High Volatility (ATR: ${atrPct.toFixed(1)}%). Recommend a wider stop-loss of <strong>${recommendedStop}%</strong> to avoid false shakeouts.</span>
                    `;
                } else {
                    suggestionEl.innerHTML = `
                        <i class="fa-solid fa-circle-info text-cyan"></i>
                        <span>Low Volatility (ATR: ${atrPct.toFixed(1)}%). Recommend a tight stop-loss of <strong>${recommendedStop}%</strong> to lock profits.</span>
                    `;
                }

                // Adjust Trend Header Badge
                const badge = document.getElementById("chart-ticker-trend");
                badge.innerText = ai.trend.toUpperCase();
                badge.className = `badge ${ai.trend.toLowerCase()}`;
            }
        }

        // Narrative text
        const explainRes = await fetch(`${API_BASE}/api/explain/${ticker}`);
        if (explainRes.ok) {
            const data = await explainRes.json();
            let html = data.explanation
                .replace(/### (.*)/g, '<h5>$1</h5>')
                .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                .replace(/• (.*)/g, '<p>• $1</p>');
            document.getElementById("narrative-content").innerHTML = html;
        }

    } catch (e) {
        console.error("AI Analysis load error:", e);
    }
}

// Fetch Portfolio stats & render Open Positions Table
async function refreshPortfolio() {
    try {
        const res = await fetch(`${API_BASE}/api/portfolio`);
        if (!res.ok) throw new Error("Portfolio load failed.");
        const data = await res.json();
        const p = data.portfolio;

        // Drawdown warning
        const drawdownWarning = document.getElementById("drawdown-warning");
        if (p.trading_frozen) {
            drawdownWarning.classList.remove("hidden");
        } else {
            drawdownWarning.classList.add("hidden");
        }

        // Drawdown slider updates from persistent backend values
        document.getElementById("slider-drawdown").value = p.drawdown_limit_pct;
        document.getElementById("lbl-drawdown-threshold").innerText = `${p.drawdown_limit_pct.toFixed(1)}%`;

        // Render cumulative Profit / Loss values at top
        const plVal = document.getElementById("port-pl-val");
        const plBadge = document.getElementById("port-pl-badge");
        const isPlPos = p.total_profit >= 0;
        plVal.innerText = `${isPlPos ? '+' : ''}$${p.total_profit.toFixed(2)} (${isPlPos ? '+' : ''}${p.total_profit_pct.toFixed(2)}%)`;
        plVal.className = isPlPos ? "text-green" : "text-red";

        // Net value summary details
        document.getElementById("port-total").innerText = `$${p.total_value.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
        document.getElementById("port-cash").innerText = `$${p.cash.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
        document.getElementById("port-holdings").innerText = `$${p.holdings_value.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
        
        // Populate open positions table
        const tbody = document.querySelector("#holdings-table tbody");
        tbody.innerHTML = "";

        const holdingsKeys = Object.keys(p.holdings);
        if (holdingsKeys.length === 0) {
            tbody.innerHTML = `
                <tr class="empty-row">
                    <td colspan="8">No active stock positions. Buy stocks above.</td>
                </tr>
            `;
            return;
        }

        holdingsKeys.forEach(ticker => {
            const h = p.holdings[ticker];
            const row = document.createElement("tr");
            
            const isProfit = h.profit >= 0;
            const profitClass = isProfit ? "text-green" : "text-red";
            const profitSign = isProfit ? "+" : "";

            row.innerHTML = `
                <td><strong>${ticker}</strong></td>
                <td>${h.shares.toFixed(4)}</td>
                <td>$${h.buy_price.toFixed(2)}</td>
                <td>$${h.current_price.toFixed(2)}</td>
                <td>$${h.value.toFixed(2)}</td>
                <td>
                    <span class="text-red">$${h.stop_loss_val.toFixed(2)}</span>
                    <small style="color: var(--text-muted); display: block;">(${h.stop_loss_pct}%)</small>
                </td>
                <td class="${profitClass}"><strong>${profitSign}$${h.profit.toFixed(2)}</strong> (${profitSign}${h.profit_pct.toFixed(2)}%)</td>
                <td>
                    <!-- Partial Sell Quantity Input Form -->
                    <div class="sell-input-group">
                        <input type="number" class="sell-qty-input" id="input-sell-qty-${ticker}" 
                               value="${h.shares.toFixed(4)}" max="${h.shares}" min="0.0001" step="0.01">
                        <button class="btn-sell-action" onclick="executePartialSell('${ticker}')">Sell</button>
                    </div>
                    <button class="row-action-btn" onclick="loadTickerData('${ticker}')" style="margin-top:0.25rem;">
                        <i class="fa-solid fa-chart-line"></i> View
                    </button>
                </td>
            `;
            tbody.appendChild(row);
        });

    } catch (e) {
        console.error("Portfolio sync error:", e);
    }
}

// Update Drawdown Limits
async function updateDrawdownSettings(val) {
    try {
        const res = await fetch(`${API_BASE}/api/settings`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ drawdown_limit_pct: val })
        });
        if (res.ok) {
            handleLiveNotification({
                type: "SYSTEM",
                title: "Settings Saved",
                message: `Persistent Daily Drawdown Limit updated to ${val.toFixed(1)}%.`
            });
            refreshPortfolio();
        }
    } catch (e) {
        console.error("Error saving settings:", e);
    }
}

// Market scanner
async function scanMarket() {
    const tbody = document.querySelector("#scanner-table tbody");
    tbody.innerHTML = `
        <tr class="empty-row">
            <td colspan="8"><i class="fa-solid fa-circle-notch fa-spin"></i> Checking market conditions...</td>
        </tr>
    `;

    try {
        const res = await fetch(`${API_BASE}/api/scan`);
        if (!res.ok) throw new Error("Scanner request failed.");
        const opportunities = await res.json();

        tbody.innerHTML = "";
        if (opportunities.length === 0) {
            tbody.innerHTML = `<tr class="empty-row"><td colspan="8">No scan results found.</td></tr>`;
            return;
        }

        opportunities.forEach(op => {
            const row = document.createElement("tr");
            
            const isUp = op.prediction === "UP";
            const predClass = isUp ? "text-green" : "text-red";
            
            const changeClass = op.change >= 0 ? "text-green" : "text-red";
            const changeSign = op.change >= 0 ? "+" : "";

            const trendClass = op.trend === "Bullish" ? "badge bullish" : (op.trend === "Bearish" ? "badge bearish" : "badge neutral");
            const candleBadge = op.pattern !== "None" ? `<span class="badge bullish">${op.pattern}</span>` : `<span style="color:var(--text-muted)">None</span>`;
            const spikeBadge = op.spike !== "None" ? `<span class="badge bearish">${op.spike}</span>` : `<span style="color:var(--text-muted)">None</span>`;

            row.innerHTML = `
                <td><strong>${op.ticker}</strong></td>
                <td>
                    $${op.price.toFixed(2)}
                    <small class="${changeClass}" style="display:block;">${changeSign}${op.change.toFixed(2)}%</small>
                </td>
                <td>${op.rsi.toFixed(1)}</td>
                <td><span class="${trendClass}">${op.trend}</span></td>
                <td>${candleBadge}</td>
                <td>
                    <span class="${predClass}"><strong>${op.prediction}</strong></span>
                    <small style="color:var(--text-muted); display:block;">${(op.confidence*100).toFixed(0)}% Conf.</small>
                </td>
                <td>${spikeBadge}</td>
                <td>
                    <button class="row-action-btn" onclick="loadTickerData('${op.ticker}')">
                        <i class="fa-solid fa-chart-line"></i> Chart
                    </button>
                </td>
            `;
            tbody.appendChild(row);
        });

    } catch (e) {
        tbody.innerHTML = `<tr class="empty-row"><td colspan="8" class="text-red">Error: ${e.message}</td></tr>`;
    }
}

// Execute buy trade
async function executeBuy() {
    const ticker = document.getElementById("order-ticker").value;
    const amount = parseFloat(document.getElementById("order-amount").value);
    const stopLoss = parseFloat(document.getElementById("order-stoploss").value);

    if (!ticker) {
        alert("Please load a stock chart first.");
        return;
    }
    if (isNaN(amount) || amount <= 0) {
        alert("Please enter a valid amount.");
        return;
    }

    try {
        const res = await fetch(`${API_BASE}/api/buy`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                ticker: ticker,
                amount: amount,
                stop_loss_pct: stopLoss
            })
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Transaction failed.");
        
        document.getElementById("order-amount").value = "";
    } catch (e) {
        alert(`Purchase Error: ${e.message}`);
    }
}

// Execute Partial Sell
async function executePartialSell(ticker) {
    const qtyInput = document.getElementById(`input-sell-qty-${ticker}`);
    const qty = parseFloat(qtyInput.value);

    if (isNaN(qty) || qty <= 0) {
        alert("Please enter a valid share quantity to sell.");
        return;
    }

    try {
        const res = await fetch(`${API_BASE}/api/sell`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                ticker: ticker,
                shares: qty
            })
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Sale failed.");
    } catch (e) {
        alert(`Sell Error: ${e.message}`);
    }
}

// Reset Account
async function resetAccount() {
    if (!confirm("Reset all holdings, trade logs, and settings to defaults?")) return;

    try {
        const res = await fetch(`${API_BASE}/api/reset`, { method: "POST" });
        if (res.ok) {
            document.getElementById("alerts-container").innerHTML = "";
            handleLiveNotification({
                type: "SYSTEM",
                title: "Portfolio Reset",
                message: "Values reverted to starting defaults."
            });
            refreshPortfolio();
        }
    } catch (e) {
        alert(`Reset Error: ${e.message}`);
    }
}

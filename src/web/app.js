// Meta-Marker Front-End Dashboard logic with WebSockets & Scrollable Chart Overlays

document.addEventListener("DOMContentLoaded", () => {
    initDashboard();
    initModalHandlers();
});

let currentSymbol = "XAUUSD";
let currentTimeframe = "M15";
let wsConnection = null;

// Global chart drag & pan state
let chartData = null;
let isDragging = false;
let dragStartX = 0;
let scrollIndex = 0; // Number of candles we have scrolled into the past (0 = show latest)
let dragAccumulator = 0; // Floating point drag pixel accumulator
const visibleCandleCount = 45; // Fixed number of candles displayed in the viewport

// Definitions mapping for explanation Modals
const TOPIC_EXPLANATIONS = {
    system: {
        title: "Meta-Marker Dashboard Overview",
        html: `
            <p>Welcome to the <strong>Meta-Marker Market Intelligence Dashboard</strong>.</p>
            <p>This analytics interface aggregates algorithmic telemetry, statistical classifications, and real-time technical indicators to provide concrete execution strategies across multiple symbols and timeframes.</p>
            <p><strong>Interactive Pan/Scroll:</strong> Click and drag left/right on the chart canvas to scroll through historical price action.</p>
        `
    },
    classification: {
        title: "Market Classification",
        html: `
            <p>Classifying market structures assists in determining which algorithms should take dominance in the current setup.</p>
            <p><strong>Primary Regime:</strong> Displays whether the market is consolidating (mean-reverting), expanding structurally, or trending aggressively.</p>
            <p><strong>Trend Classification:</strong> Tracks micro-structures such as Higher Highs, Lower Lows, or structural breaks.</p>
        `
    },
    confidence: {
        title: "Confidence Engine",
        html: `
            <p>The <strong>Confidence Engine</strong> compiles mathematical inputs across all sub-indicators and ranks active directional flow.</p>
            <p>The dial shows dynamic weighted results based on dynamic reliability scores updated in the database.</p>
        `
    },
    recommendation: {
        title: "Actionable Recommendation",
        html: `
            <p>The <strong>Actionable Recommendation</strong> processes underlying volatility, momentum ranges, and dynamic indicator weights to propose clear, systematic guidelines.</p>
        `
    },
    chart: {
        title: "Live Price Action Chart",
        html: `
            <p>Renders real-time candlestick history directly. In addition to candles, it overlays:
                <ul>
                    <li><strong style="color: #ffd700;">EMA 20 (Gold Line)</strong>: Short-term momentum filter.</li>
                    <li><strong style="color: #a855f7;">EMA 50 (Purple Line)</strong>: Medium-term trend bias filter.</li>
                    <li><strong style="color: rgba(5,255,197,0.7);">Support Levels (Green Dashed)</strong>: Key horizontal buying floors.</li>
                    <li><strong style="color: rgba(255,59,48,0.7);">Resistance Levels (Red Dashed)</strong>: Key horizontal selling ceilings.</li>
                </ul>
            </p>
        `
    },
    indicators: {
        title: "Indicator Matrix & Dynamic Scores Overview",
        html: `
            <p>The <strong>Indicator Matrix</strong> evaluates multiple non-correlated technical algorithms across every closed bar.</p>
            <p>Click any indicator row or column header in the table to display its exact mathematical formula, signal thresholds, and reliability weight calculations.</p>
        `
    },
    // Indicator Specific Modal Guides
    ind_sma: {
        title: "SMA (Simple Moving Average 20 / 50)",
        html: `
            <p><strong>Simple Moving Average (SMA)</strong> calculates the unweighted arithmetic mean of closing prices over 20 and 50 period windows.</p>
            <div class="modal-badge-group">
                <span class="modal-badge badge-buy">BUY Signal</span> Fast SMA (20) crosses above Slow SMA (50) — Golden Cross alignment.
            </div>
            <div class="modal-badge-group">
                <span class="modal-badge badge-sell">SELL Signal</span> Fast SMA (20) crosses below Slow SMA (50) — Death Cross alignment.
            </div>
            <p style="margin-top: 10px;"><strong>Formula:</strong> <code>SMA = (P1 + P2 + ... + Pn) / n</code></p>
        `
    },
    ind_ema: {
        title: "EMA Cross (Exponential Moving Average 20 vs 50)",
        html: `
            <p><strong>EMA Cross</strong> measures short-term price momentum against medium-term trend bias by calculating the delta between the 20-period EMA and the 50-period EMA.</p>
            <div class="modal-badge-group">
                <span class="modal-badge badge-buy">BUY Signal</span> EMA 20 > EMA 50 (Positive Delta). Short-term momentum is above medium-term trend bias.
            </div>
            <div class="modal-badge-group">
                <span class="modal-badge badge-sell">SELL Signal</span> EMA 20 < EMA 50 (Negative Delta). Short-term momentum is below medium-term trend bias.
            </div>
            <p style="margin-top: 10px;"><strong>Value Field:</strong> Displays the raw price spread <code>(EMA_20 - EMA_50)</code>.</p>
        `
    },
    ind_stoch: {
        title: "Stochastic Oscillator (%K 14, %D 3)",
        html: `
            <p><strong>Stochastic Oscillator</strong> compares a security's closing price to its high-low price range over a 14-period window, pinpointing overbought and oversold momentum turning points.</p>
            <div class="modal-badge-group">
                <span class="modal-badge badge-buy">BUY Signal</span> %K line < 20 (Oversold condition) AND crosses above the %D signal line.
            </div>
            <div class="modal-badge-group">
                <span class="modal-badge badge-sell">SELL Signal</span> %K line > 80 (Overbought condition) AND crosses below the %D signal line.
            </div>
            <p style="margin-top: 10px;"><strong>Value Field:</strong> Current %K value bounded between 0 and 100.</p>
        `
    },
    ind_rsi: {
        title: "RSI (Relative Strength Index - 14 Period)",
        html: `
            <p><strong>Relative Strength Index (RSI)</strong> measures speed and momentum of price movements on a scale of 0 to 100.</p>
            <div class="modal-badge-group">
                <span class="modal-badge badge-buy">BUY Signal</span> RSI < 30 (Oversold reversal) OR bullish crossover above centerline 50.
            </div>
            <div class="modal-badge-group">
                <span class="modal-badge badge-sell">SELL Signal</span> RSI > 70 (Overbought reversal) OR bearish crossover below centerline 50.
            </div>
            <p style="margin-top: 10px;"><strong>Formula:</strong> <code>RSI = 100 - (100 / (1 + RS))</code> where <code>RS = Avg Gain / Avg Loss</code></p>
        `
    },
    ind_macd: {
        title: "MACD (Moving Average Convergence Divergence 12, 26, 9)",
        html: `
            <p><strong>MACD</strong> evaluates relationship dynamics between two exponential moving averages. The histogram measures the delta between the MACD line and 9-period Signal line.</p>
            <div class="modal-badge-group">
                <span class="modal-badge badge-buy">BUY Signal</span> MACD Line crosses above Signal Line (Positive Histogram Expansion).
            </div>
            <div class="modal-badge-group">
                <span class="modal-badge badge-sell">SELL Signal</span> MACD Line crosses below Signal Line (Negative Histogram Expansion).
            </div>
        `
    },
    ind_atr: {
        title: "ATR (Average True Range - 14 Period)",
        html: `
            <p><strong>Average True Range (ATR)</strong> decomposes total market volatility across 14 periods.</p>
            <div class="modal-badge-group">
                <span class="modal-badge badge-neutral">VOLATILITY METRIC</span> Used systematically to compute dynamic Stop Losses (e.g. <code>2.0 * ATR</code>) and Take Profit targets.
            </div>
            <p style="margin-top: 10px;"><strong>Formula:</strong> <code>TR = Max(High - Low, |High - PrevClose|, |Low - PrevClose|)</code></p>
        `
    },
    ind_structure: {
        title: "Market Structure (Swing Sequence)",
        html: `
            <p><strong>Market Structure Alignment</strong> evaluates structural sequences of Higher Highs (HH), Higher Lows (HL), Lower Highs (LH), and Lower Lows (LL).</p>
            <div class="modal-badge-group">
                <span class="modal-badge badge-buy">BUY Signal</span> Bullish structure confirmed via consecutive Higher Highs & Higher Lows.
            </div>
            <div class="modal-badge-group">
                <span class="modal-badge badge-sell">SELL Signal</span> Bearish structure confirmed via consecutive Lower Highs & Lower Lows.
            </div>
        `
    },
    ind_swing: {
        title: "Swing Support & Resistance Levels",
        html: `
            <p><strong>Swing Levels</strong> detect key historical price points where buying interest (Support) or selling pressure (Resistance) previously triggered reversals.</p>
            <div class="modal-badge-group">
                <span class="modal-badge badge-buy">BUY Signal</span> Price retests Support floor with bullish rejection.
            </div>
            <div class="modal-badge-group">
                <span class="modal-badge badge-sell">SELL Signal</span> Price retests Resistance ceiling with bearish rejection.
            </div>
        `
    },
    // Matrix Column Explanations
    col_indicator: {
        title: "Column Definition: INDICATOR",
        html: `
            <p>The specific technical analysis indicator or structural algorithm evaluated across active price history.</p>
            <p>Clicking any indicator name or info icon displays its exact calculation rules, mathematical formulas, and signal thresholds.</p>
        `
    },
    col_signal: {
        title: "Column Definition: SIGNAL",
        html: `
            <p>The directional bias output generated by evaluating the metric against current price action:</p>
            <ul>
                <li><strong style="color: #05ffc5;">BUY:</strong> Bullish convergence condition met.</li>
                <li><strong style="color: #ff3b30;">SELL:</strong> Bearish convergence condition met.</li>
                <li><strong style="color: #00f0ff;">NEUTRAL:</strong> Inconclusive range or mixed indicator values.</li>
            </ul>
        `
    },
    col_value: {
        title: "Column Definition: VALUE",
        html: `
            <p>The exact raw mathematical numerical result computed for the indicator on the latest closed candle bar.</p>
        `
    },
    col_reliability: {
        title: "Column Definition: DYNAMIC RELIABILITY",
        html: `
            <p><strong>Dynamic Reliability</strong> represents the empirical win-rate accuracy of this specific indicator in the active market regime.</p>
            <p><strong>Real-Time Resolution Engine:</strong></p>
            <ul>
                <li>Every recommendation generated is saved to an internal SQLite <code>prediction_audit</code> table with timestamps, entry price, Stop Loss, Take Profit, and initial indicator signals.</li>
                <li>As new market candles ingest from MT5, pending predictions are evaluated against live price highs and lows.</li>
                <li>When Take Profit or Stop Loss is reached, the prediction resolves (<code>SUCCESS_TP</code> or <code>FAIL_SL</code>), and the win-rate score for each contributing indicator is updated in SQLite.</li>
            </ul>
        `
    }
};

async function initDashboard() {
    setupSelectors();
    setupChartInteractions();
    setupViewNavigation();
    setupAuditHandlers();
    fetchEngineHealth();
    await fetchActiveTargets();
    await fetchBrokerSymbols();
    await fetchDashboardData();
    connectWebSocket();
}

// Setup selector dropdown change events and dynamic add symbol input
function setupSelectors() {
    const symSelect = document.getElementById("symbol-select");
    const tfSelect = document.getElementById("timeframe-select");
    const addInput = document.getElementById("add-symbol-input");
    const addBtn = document.getElementById("add-symbol-btn");

    symSelect.addEventListener("change", (e) => {
        currentSymbol = e.target.value;
        scrollIndex = 0; // Reset scroll on asset change
        updateHeaderStatus();
        fetchDashboardData();
    });

    tfSelect.addEventListener("change", (e) => {
        currentTimeframe = e.target.value;
        scrollIndex = 0; // Reset scroll on timeframe change
        updateHeaderStatus();
        fetchDashboardData();
    });

    addBtn.addEventListener("click", async () => {
        const value = addInput.value.trim().toUpperCase();
        if (value) {
            try {
                const res = await fetch("/api/monitor/add", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ symbol: value, timeframe: currentTimeframe })
                });
                if (res.ok) {
                    addInput.value = "";
                    await fetchActiveTargets();
                    symSelect.value = value;
                    currentSymbol = value;
                    scrollIndex = 0;
                    updateHeaderStatus();
                    fetchDashboardData();
                }
            } catch (err) {
                console.error("Failed to add symbol:", err);
            }
        }
    });
}

// Setup drag, swipe, and wheel interactions on the canvas
function setupChartInteractions() {
    const canvas = document.getElementById("price-chart");
    if (!canvas) return;

    const startDrag = (clientX) => {
        isDragging = true;
        dragStartX = clientX;
        dragAccumulator = -scrollIndex; // Initialize accumulator to current scroll index
        canvas.style.cursor = "grabbing";
    };

    const moveDrag = (clientX) => {
        if (!isDragging || !chartData || !chartData.history) return;
        
        const deltaX = clientX - dragStartX;
        dragStartX = clientX; // Always advance dragStartX continuously
        
        const rectWidth = canvas.width || 800;
        const widthPerCandle = (rectWidth - 70) / visibleCandleCount;
        if (widthPerCandle <= 0) return;
        
        // Dragging left (deltaX < 0) means looking into past -> increase scrollIndex
        const candlesMoved = deltaX / widthPerCandle;
        dragAccumulator -= candlesMoved;
        
        const historyLength = chartData.history.length;
        const maxScroll = Math.max(0, historyLength - visibleCandleCount);
        
        const newScrollIndex = Math.max(0, Math.min(maxScroll, Math.round(dragAccumulator)));
        if (newScrollIndex !== scrollIndex) {
            scrollIndex = newScrollIndex;
            drawChart(chartData);
        }
    };

    const stopDrag = () => {
        isDragging = false;
        canvas.style.cursor = "crosshair";
    };

    // Mouse drag events
    canvas.addEventListener("mousedown", (e) => startDrag(e.clientX));
    canvas.addEventListener("mousemove", (e) => moveDrag(e.clientX));
    window.addEventListener("mouseup", stopDrag);
    canvas.addEventListener("mouseleave", stopDrag);

    // Touch swipe events
    canvas.addEventListener("touchstart", (e) => {
        if (e.touches.length === 1) startDrag(e.touches[0].clientX);
    }, { passive: true });
    canvas.addEventListener("touchmove", (e) => {
        if (e.touches.length === 1) moveDrag(e.touches[0].clientX);
    }, { passive: true });
    canvas.addEventListener("touchend", stopDrag);

    // Wheel / Touchpad scroll events
    canvas.addEventListener("wheel", (e) => {
        if (!chartData || !chartData.history) return;
        e.preventDefault();
        
        const historyLength = chartData.history.length;
        const maxScroll = Math.max(0, historyLength - visibleCandleCount);
        
        // Scroll down / right = view past candles (+scrollIndex)
        // Scroll up / left = view latest candles (-scrollIndex)
        const direction = e.deltaY > 0 || e.deltaX > 0 ? 1 : -1;
        const shift = Math.abs(e.deltaY) > 50 ? 3 : 1;
        
        scrollIndex = Math.max(0, Math.min(maxScroll, scrollIndex + direction * shift));
        dragAccumulator = scrollIndex;
        drawChart(chartData);
    }, { passive: false });
}

function updateHeaderStatus() {
    const statusText = document.getElementById("header-status-text");
    statusText.textContent = `MIE LIVE (${currentTimeframe} ${currentSymbol})`;
}

async function fetchActiveTargets() {
    try {
        const response = await fetch("/api/monitor/targets");
        if (response.ok) {
            const targets = await response.json();
            const symSelect = document.getElementById("symbol-select");
            
            // Get all existing option values in dropdown
            const existingValues = Array.from(symSelect.querySelectorAll("option")).map(opt => opt.value);
            const serverSymbols = [...new Set(targets.map(t => t.symbol))];
            
            // Find custom symbols not yet in the select
            const customSymbols = serverSymbols.filter(s => !existingValues.includes(s));
            if (customSymbols.length > 0) {
                let customGroup = symSelect.querySelector("optgroup[label='Custom Markets']");
                if (!customGroup) {
                    customGroup = document.createElement("optgroup");
                    customGroup.label = "Custom Markets";
                    symSelect.appendChild(customGroup);
                }
                customSymbols.forEach(sym => {
                    const opt = document.createElement("option");
                    opt.value = sym;
                    opt.textContent = sym;
                    customGroup.appendChild(opt);
                });
            }
        }
    } catch (err) {
        console.error("Failed to load targets:", err);
    }
}

async function fetchBrokerSymbols() {
    try {
        const response = await fetch("/api/broker/symbols");
        if (response.ok) {
            const allSymbols = await response.json();
            const addInput = document.getElementById("add-symbol-input");
            let datalist = document.getElementById("broker-symbols-datalist");
            if (!datalist) {
                datalist = document.createElement("datalist");
                datalist.id = "broker-symbols-datalist";
                document.body.appendChild(datalist);
            }
            datalist.innerHTML = "";
            allSymbols.slice(0, 50).forEach(sym => {
                const opt = document.createElement("option");
                opt.value = sym;
                datalist.appendChild(opt);
            });
            addInput.setAttribute("list", "broker-symbols-datalist");
        }
    } catch (err) {}
}

async function fetchDashboardData() {
    try {
        const response = await fetch(`/api/state?symbol=${currentSymbol}&timeframe=${currentTimeframe}`);
        if (!response.ok) {
            displayWaitingState();
            return;
        }
        const data = await response.json();
        chartData = data; // Cache data
        updateUI(data);
        drawChart(data);
    } catch (err) {
        console.error("Dashboard data load error:", err);
        displayWaitingState();
    }
}

// Websocket logic
function connectWebSocket() {
    const loc = window.location;
    const wsUri = (loc.protocol === "https:" ? "wss://" : "ws://") + loc.host + "/ws";
    
    wsConnection = new WebSocket(wsUri);

    wsConnection.onmessage = (event) => {
        try {
            const payload = JSON.parse(event.data);
            if (payload.symbol.toUpperCase() === currentSymbol.toUpperCase() && payload.timeframe === currentTimeframe) {
                chartData = payload; // Update cached data
                updateUI(payload);
                drawChart(payload);
            }
        } catch (e) {
            console.error("WebSocket message parse error:", e);
        }
    };

    wsConnection.onclose = () => {
        setTimeout(connectWebSocket, 5000);
    };

    wsConnection.onerror = (err) => {
        console.error("WebSocket error:", err);
        wsConnection.close();
    };
}

// Modal handlers
function initModalHandlers() {
    const modal = document.getElementById("info-modal");
    const modalTitle = document.getElementById("modal-title");
    const modalText = document.getElementById("modal-text");
    const closeBtn = document.getElementById("modal-close-btn");
    const guideBtn = document.getElementById("open-guide-btn");

    function openModal(topicKey) {
        const info = TOPIC_EXPLANATIONS[topicKey];
        if (info) {
            modalTitle.textContent = info.title;
            modalText.innerHTML = info.html;
            modal.classList.add("active");
        }
    }

    function closeModal() {
        modal.classList.remove("active");
    }

    // Event delegation for static and dynamically created info triggers
    document.addEventListener("click", (e) => {
        const trigger = e.target.closest(".info-trigger");
        if (trigger) {
            e.stopPropagation();
            const topic = trigger.getAttribute("data-topic");
            openModal(topic);
        }
    });

    if (guideBtn) {
        guideBtn.addEventListener("click", () => {
            openModal("system");
        });
    }

    if (closeBtn) closeBtn.addEventListener("click", closeModal);
    modal.addEventListener("click", (e) => {
        if (e.target === modal) closeModal();
    });
}

function displayWaitingState() {
    document.getElementById("market-regime").textContent = "WAITING";
    document.getElementById("market-trend-state").textContent = "Waiting for candles to ingest...";
    document.getElementById("market-volatility").textContent = "---";
    document.getElementById("market-momentum").textContent = "---";
    document.getElementById("buy-confidence-val").textContent = "--%";
    document.getElementById("buy-val").textContent = "--%";
    document.getElementById("sell-val").textContent = "--%";
    document.getElementById("dial-recommendation").textContent = "HOLD";
    document.getElementById("recommendation-text").innerHTML = `
        <div style="font-size: 14px;">
            <p><strong>No data ingested for ${currentSymbol} on ${currentTimeframe}.</strong></p>
            <p style="margin-top: 8px; color: var(--text-secondary);">Ensure your MetaTrader 5 terminal is connected, DLL imports are enabled, and the sync target is active.</p>
        </div>
    `;
    
    // Clear indicator matrix table
    const tbody = document.getElementById("indicators-body");
    if (tbody) {
        tbody.innerHTML = `<tr><td colspan="4" class="empty-state">No indicator data loaded. Waiting for ingestion...</td></tr>`;
    }
    
    const canvas = document.getElementById("price-chart");
    if (canvas) {
        const ctx = canvas.getContext("2d");
        ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
}

function updateUI(data) {
    document.getElementById("market-regime").textContent = data.classification.primary_regime.toUpperCase();
    document.getElementById("market-trend-state").textContent = data.classification.trend_state;
    document.getElementById("market-volatility").textContent = data.classification.volatility_state.toUpperCase();
    document.getElementById("market-momentum").textContent = data.classification.momentum_state.toUpperCase();

    const buyConf = Math.round(data.confidence_buy);
    const sellConf = Math.round(data.confidence_sell);

    document.getElementById("buy-val").textContent = `${buyConf}%`;
    document.getElementById("sell-val").textContent = `${sellConf}%`;

    const circleFill = document.getElementById("buy-dial");
    const strokeOffset = 251 - (251 * buyConf / 100);
    circleFill.style.strokeDashoffset = strokeOffset;

    const dialVal = document.getElementById("buy-confidence-val");
    const dialRec = document.getElementById("dial-recommendation");
    dialVal.textContent = `${buyConf}%`;

    if (buyConf > 60) {
        circleFill.style.stroke = "var(--color-green)";
        dialRec.textContent = "BUY CONFD";
        dialRec.style.color = "var(--color-green)";
    } else if (sellConf > 60) {
        circleFill.style.stroke = "var(--color-red)";
        dialVal.textContent = `${sellConf}%`;
        dialRec.textContent = "SELL CONFD";
        dialRec.style.color = "var(--color-red)";
        circleFill.style.strokeDashoffset = 251 - (251 * sellConf / 100);
    } else {
        circleFill.style.stroke = "var(--color-cyan)";
        dialRec.textContent = "NEUTRAL";
        dialRec.style.color = "var(--color-cyan)";
    }

    const recBox = document.getElementById("recommendation-text");
    recBox.textContent = data.recommendation;
    if (data.recommendation.includes("BUY")) {
        recBox.style.background = "rgba(5, 255, 197, 0.05)";
        recBox.style.borderColor = "rgba(5, 255, 197, 0.25)";
        recBox.style.color = "var(--color-green)";
    } else if (data.recommendation.includes("SELL")) {
        recBox.style.background = "rgba(255, 59, 48, 0.05)";
        recBox.style.borderColor = "rgba(255, 59, 48, 0.25)";
        recBox.style.color = "var(--color-red)";
    } else {
        recBox.style.background = "rgba(0, 240, 255, 0.05)";
        recBox.style.borderColor = "rgba(0, 240, 255, 0.15)";
        recBox.style.color = "var(--color-cyan)";
    }

    const tbody = document.getElementById("indicators-body");
    tbody.innerHTML = "";

    const keyTopicMap = {
        "EMA_Cross": "ind_ema",
        "EMA_20_50": "ind_ema",
        "RSI": "ind_rsi",
        "MACD": "ind_macd",
        "Stochastic": "ind_stoch",
        "Market_Structure": "ind_structure",
        "SMA_20_50": "ind_sma",
        "ATR": "ind_atr",
        "Swing_Levels": "ind_swing"
    };

    Object.keys(data.indicator_signals).forEach(key => {
        const sig = data.indicator_signals[key];
        const row = document.createElement("tr");

        let sigClass = "sig-neutral";
        if (sig.signal === "BUY") sigClass = "sig-buy";
        else if (sig.signal === "SELL") sigClass = "sig-sell";

        let displayVal = sig.value.toFixed(2);
        if (key === "Market_Structure") displayVal = "Aligned";
        
        const topicKey = keyTopicMap[key] || "system";

        row.innerHTML = `
            <td>
                <button class="table-info-btn info-trigger" data-topic="${topicKey}" title="View indicator formula & breakdown">ⓘ</button>
                <strong class="indicator-name-link info-trigger" data-topic="${topicKey}">${sig.name.replace(/_/g, " ")}</strong>
            </td>
            <td><span class="sig-badge ${sigClass}">${sig.signal}</span></td>
            <td><code>${displayVal}</code></td>
            <td style="font-weight: 800; color: var(--color-cyan);">${Math.round(sig.confidence * 100)}%</td>
        `;
        tbody.appendChild(row);
    });
}

// Indicator overlay calculators helper
function calculateEMA(prices, period) {
    if (prices.length < period) return [];
    const emas = [];
    const k = 2 / (period + 1);
    let sum = 0;
    for (let i = 0; i < period; i++) sum += prices[i];
    emas.push(sum / period);
    for (let i = period; i < prices.length; i++) {
        emas.push((prices[i] - emas[emas.length - 1]) * k + emas[emas.length - 1]);
    }
    return emas;
}

function identifySwingLevels(history) {
    const supports = [];
    const resistances = [];
    for (let i = 4; i < history.length - 4; i++) {
        const currentHigh = history[i].high;
        const currentLow = history[i].low;
        let isHigh = true;
        let isLow = true;
        
        for (let j = -4; j <= 4; j++) {
            if (j === 0) continue;
            if (history[i + j].high > currentHigh) isHigh = false;
            if (history[i + j].low < currentLow) isLow = false;
        }
        if (isHigh) resistances.push(currentHigh);
        if (isLow) supports.push(currentLow);
    }
    return { 
        supports: [...new Set(supports)].slice(-4), 
        resistances: [...new Set(resistances)].slice(-4) 
    };
}

function drawChart(data) {
    const canvas = document.getElementById("price-chart");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width;
    canvas.height = rect.height;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const width = canvas.width;
    const height = canvas.height;

    const paddingLeft = 10;
    const paddingRight = 60; // Space for price scale labels
    const paddingTop = 25;
    const paddingBottom = 25;

    const chartWidth = width - paddingLeft - paddingRight;
    const chartHeight = height - paddingTop - paddingBottom;

    const history = data.history || [];
    if (history.length === 0) return;

    // Slice history to only show the viewport window (visibleCandleCount) based on scrollIndex
    const endIdx = Math.max(visibleCandleCount, history.length - scrollIndex);
    const startIdx = Math.max(0, endIdx - visibleCandleCount);
    const visibleHistory = history.slice(startIdx, endIdx);
    
    if (visibleHistory.length === 0) return;

    // Find min and max prices within the visible window to scale y-axis
    let minPrice = Math.min(...visibleHistory.map(c => c.low));
    let maxPrice = Math.max(...visibleHistory.map(c => c.high));

    // If trade setup is active, expand scale to include stop loss and take profit
    if (data.trade_setup) {
        minPrice = Math.min(minPrice, data.trade_setup.stop_loss, data.trade_setup.take_profit);
        maxPrice = Math.max(maxPrice, data.trade_setup.stop_loss, data.trade_setup.take_profit);
    }

    const priceRange = maxPrice - minPrice;
    const priceMargin = priceRange * 0.1 || 1.0;
    minPrice -= priceMargin;
    maxPrice += priceMargin;

    const scaleY = (price) => {
        return chartHeight - ((price - minPrice) / (maxPrice - minPrice)) * chartHeight + paddingTop;
    };

    // Helper: Draw label text box with a solid background for readability
    const drawTextBox = (text, x, y, color, alignment = "left") => {
        ctx.font = "bold 10px Outfit, sans-serif";
        ctx.textBaseline = "middle";
        ctx.textAlign = alignment;
        
        const textWidth = ctx.measureText(text).width;
        const boxWidth = textWidth + 8;
        const boxHeight = 16;
        
        ctx.fillStyle = "rgba(10, 14, 23, 0.9)";
        
        let boxX = x;
        if (alignment === "right") {
            boxX = x - boxWidth;
        } else if (alignment === "center") {
            boxX = x - boxWidth / 2;
        }
        
        ctx.fillRect(boxX, y - boxHeight / 2, boxWidth, boxHeight);
        ctx.strokeStyle = color;
        ctx.lineWidth = 0.5;
        ctx.strokeRect(boxX, y - boxHeight / 2, boxWidth, boxHeight);
        
        ctx.fillStyle = "#ffffff"; // Brighter white text for readability
        ctx.fillText(text, alignment === "right" ? x - 4 : (alignment === "center" ? x : x + 4), y);
    };

    // Draw background grid lines & Price scale Labels
    ctx.strokeStyle = "rgba(255, 255, 255, 0.04)";
    ctx.lineWidth = 1;
    
    const gridLinesCount = 5;
    for (let i = 0; i < gridLinesCount; i++) {
        const ratio = i / (gridLinesCount - 1);
        const price = maxPrice - ratio * (maxPrice - minPrice);
        const y = scaleY(price);
        
        // Draw gridline
        ctx.beginPath();
        ctx.moveTo(paddingLeft, y);
        ctx.lineTo(paddingLeft + chartWidth, y);
        ctx.stroke();
        
        // Draw bright y-axis price scale label on the right
        ctx.fillStyle = "#ffffff";
        ctx.font = "10px Outfit, sans-serif";
        ctx.textAlign = "left";
        ctx.textBaseline = "middle";
        ctx.fillText(price.toFixed(2), paddingLeft + chartWidth + 6, y);
    }

    const candleWidth = chartWidth / visibleHistory.length;
    const bodyPadding = Math.max(1, candleWidth * 0.2);

    // Calculate indicator overlay lines on full history to keep EMA curves continuous
    const allCloses = history.map(c => c.close);
    const ema20 = calculateEMA(allCloses, 20);
    const ema50 = calculateEMA(allCloses, 50);
    const structure = identifySwingLevels(history);

    // 1. Draw Support and Resistance zones overlay (dashed lines with clean labels)
    ctx.lineWidth = 1;
    structure.supports.forEach(level => {
        const y = scaleY(level);
        ctx.strokeStyle = "rgba(5, 255, 197, 0.35)";
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.moveTo(paddingLeft, y);
        ctx.lineTo(paddingLeft + chartWidth, y);
        ctx.stroke();
        ctx.setLineDash([]);
        
        drawTextBox(`SUP: ${level.toFixed(2)}`, paddingLeft + 5, y, "#05ffc5", "left");
    });

    structure.resistances.forEach(level => {
        const y = scaleY(level);
        ctx.strokeStyle = "rgba(255, 59, 48, 0.35)";
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.moveTo(paddingLeft, y);
        ctx.lineTo(paddingLeft + chartWidth, y);
        ctx.stroke();
        ctx.setLineDash([]);
        
        drawTextBox(`RES: ${level.toFixed(2)}`, paddingLeft + 5, y, "#ff3b30", "left");
    });

    // 2. Draw active trade execution setup parameters (ENTRY, SL, TP)
    if (data.trade_setup) {
        // Stop Loss Line
        const ySL = scaleY(data.trade_setup.stop_loss);
        ctx.strokeStyle = "#ff3b30";
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(paddingLeft, ySL);
        ctx.lineTo(paddingLeft + chartWidth, ySL);
        ctx.stroke();
        drawTextBox(`SL: ${data.trade_setup.stop_loss.toFixed(2)}`, paddingLeft + chartWidth - 5, ySL, "#ff3b30", "right");
        
        // Take Profit Line
        const yTP = scaleY(data.trade_setup.take_profit);
        ctx.strokeStyle = "#05ffc5";
        ctx.beginPath();
        ctx.moveTo(paddingLeft, yTP);
        ctx.lineTo(paddingLeft + chartWidth, yTP);
        ctx.stroke();
        drawTextBox(`TP: ${data.trade_setup.take_profit.toFixed(2)}`, paddingLeft + chartWidth - 5, yTP, "#05ffc5", "right");
        
        // Entry Line
        const yEntry = scaleY(data.trade_setup.entry);
        ctx.strokeStyle = "#ffd700";
        ctx.beginPath();
        ctx.moveTo(paddingLeft, yEntry);
        ctx.lineTo(paddingLeft + chartWidth, yEntry);
        ctx.stroke();
        drawTextBox(`ENTRY: ${data.trade_setup.entry.toFixed(2)}`, paddingLeft + chartWidth - 5, yEntry, "#ffd700", "right");
    }

    // 3. Draw Candlesticks
    visibleHistory.forEach((candle, idx) => {
        const x = paddingLeft + idx * candleWidth + candleWidth / 2;
        const yOpen = scaleY(candle.open);
        const yClose = scaleY(candle.close);
        const yHigh = scaleY(candle.high);
        const yLow = scaleY(candle.low);

        const isBullish = candle.close >= candle.open;
        const color = isBullish ? "#05ffc5" : "#ff3b30";

        ctx.strokeStyle = color;
        ctx.fillStyle = color;
        ctx.lineWidth = 1.5;

        // Draw Wick
        ctx.beginPath();
        ctx.moveTo(x, yHigh);
        ctx.lineTo(x, yLow);
        ctx.stroke();

        // Draw Body
        const bodyWidth = candleWidth - bodyPadding * 2;
        const bodyHeight = Math.max(1.5, Math.abs(yClose - yOpen));
        const bodyX = x - bodyWidth / 2;
        const bodyY = Math.min(yOpen, yClose);
        ctx.fillRect(bodyX, bodyY, bodyWidth, bodyHeight);

        // Draw Time labels on X-axis (spaced every 6 candles for clean layout)
        if (idx % 6 === 0) {
            ctx.fillStyle = "#ffffff";
            ctx.font = "bold 9px Outfit, sans-serif";
            ctx.textAlign = "center";
            ctx.textBaseline = "top";
            try {
                const date = new Date(candle.time);
                const hrs = String(date.getUTCHours()).padStart(2, '0');
                const mins = String(date.getUTCMinutes()).padStart(2, '0');
                ctx.fillText(`${hrs}:${mins}`, x, paddingBottom + chartHeight + 6);
            } catch (e) {}
        }
    });

    // 4. Draw EMA curves overlay
    // Draw EMA 20 (Gold line)
    if (ema20.length > 0) {
        ctx.strokeStyle = "#ffd700";
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        let firstDrawn = false;
        
        for (let i = 0; i < visibleHistory.length; i++) {
            // Map visible candle index to absolute history index
            const absIdx = startIdx + i;
            const emaIdx = absIdx - (history.length - ema20.length);
            if (emaIdx >= 0 && emaIdx < ema20.length) {
                const x = paddingLeft + i * candleWidth + candleWidth/2;
                if (!firstDrawn) {
                    ctx.moveTo(x, scaleY(ema20[emaIdx]));
                    firstDrawn = true;
                } else {
                    ctx.lineTo(x, scaleY(ema20[emaIdx]));
                }
            }
        }
        ctx.stroke();
    }

    // Draw EMA 50 (Purple line)
    if (ema50.length > 0) {
        ctx.strokeStyle = "#a855f7";
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        let firstDrawn = false;
        
        for (let i = 0; i < visibleHistory.length; i++) {
            const absIdx = startIdx + i;
            const emaIdx = absIdx - (history.length - ema50.length);
            if (emaIdx >= 0 && emaIdx < ema50.length) {
                const x = paddingLeft + i * candleWidth + candleWidth/2;
                if (!firstDrawn) {
                    ctx.moveTo(x, scaleY(ema50[emaIdx]));
                    firstDrawn = true;
                } else {
                    ctx.lineTo(x, scaleY(ema50[emaIdx]));
                }
            }
        }
        ctx.stroke();
    }
}

// ==========================================
// Multi-View Navigation & Audit Telemetry
// ==========================================

function setupViewNavigation() {
    const tabs = document.querySelectorAll(".nav-tab");
    tabs.forEach(tab => {
        tab.addEventListener("click", () => {
            const targetView = tab.getAttribute("data-view");
            tabs.forEach(t => t.classList.remove("active"));
            tab.classList.add("active");

            document.querySelectorAll(".view-panel").forEach(panel => {
                panel.classList.remove("active");
            });

            const activePanel = document.getElementById(`view-${targetView}`);
            if (activePanel) {
                activePanel.classList.add("active");
            }

            if (targetView === "audit") {
                fetchAuditData();
            } else if (targetView === "diagnostics") {
                fetchDiagnosticsData();
            }
        });
    });
}

function setupAuditHandlers() {
    const refreshBtn = document.getElementById("refresh-audit-btn");
    if (refreshBtn) {
        refreshBtn.addEventListener("click", () => {
            fetchAuditData();
        });
    }
}

async function fetchEngineHealth() {
    try {
        const res = await fetch("/api/health");
        if (res.ok) {
            const data = await res.json();
            const badge = document.getElementById("engine-mode-badge");
            if (badge) {
                if (data.is_synthetic) {
                    badge.textContent = "SYNTHETIC SIM";
                    badge.classList.add("synthetic");
                } else {
                    badge.textContent = "LIVE MT5";
                    badge.classList.remove("synthetic");
                }
            }
        }
    } catch (e) {
        console.warn("Failed to query engine health:", e);
    }
}

async function fetchAuditData() {
    const totalEl = document.getElementById("audit-total-count");
    const resolvedEl = document.getElementById("audit-resolved-count");
    const winRateEl = document.getElementById("audit-win-rate");
    const tableBody = document.getElementById("audit-table-body");

    try {
        const res = await fetch("/api/predictions/history?limit=50");
        if (res.ok) {
            const data = await res.json();
            if (totalEl) totalEl.textContent = data.total_audited;
            if (resolvedEl) resolvedEl.textContent = data.resolved_count;
            if (winRateEl) winRateEl.textContent = `${data.win_rate}%`;

            if (tableBody) {
                if (!data.predictions || data.predictions.length === 0) {
                    tableBody.innerHTML = `<tr><td colspan="10" class="empty-state">No predictions audited yet. Waiting for candle transitions...</td></tr>`;
                    return;
                }

                tableBody.innerHTML = "";
                data.predictions.forEach(p => {
                    const tr = document.createElement("tr");
                    let statusClass = "status-pending";
                    if (p.status === "SUCCESS_TP") statusClass = "status-success";
                    else if (p.status === "FAIL_SL") statusClass = "status-fail";

                    const recShort = (p.recommendation || "").replace("★ MAX CONFIDENCE SETUP ★ ", "").substring(0, 32);
                    const slStr = p.stop_loss ? p.stop_loss.toFixed(2) : "---";
                    const tpStr = p.take_profit ? p.take_profit.toFixed(2) : "---";
                    const entryStr = p.entry_price ? p.entry_price.toFixed(2) : "---";

                    tr.innerHTML = `
                        <td style="color: var(--text-secondary); font-family: monospace;">#${p.id}</td>
                        <td style="font-weight: 700;">${p.symbol}</td>
                        <td style="color: var(--color-cyan);">${p.timeframe}</td>
                        <td style="color: var(--text-secondary); font-size: 12px;">${p.primary_regime}</td>
                        <td style="font-size: 12px;">${recShort}</td>
                        <td style="font-family: monospace;">${entryStr}</td>
                        <td style="font-family: monospace; color: var(--color-red);">${slStr}</td>
                        <td style="font-family: monospace; color: var(--color-green);">${tpStr}</td>
                        <td style="font-size: 12px; font-weight: 600;">${p.buy_confidence > 50 ? `${p.buy_confidence.toFixed(0)}% BUY` : `${p.sell_confidence.toFixed(0)}% SELL`}</td>
                        <td><span class="status-pill ${statusClass}">${p.status}</span></td>
                    `;
                    tableBody.appendChild(tr);
                });
            }
        }
    } catch (err) {
        console.error("Failed to load prediction audit history:", err);
    }
}

async function fetchDiagnosticsData() {
    try {
        const [healthRes, diagRes] = await Promise.all([
            fetch("/api/health"),
            fetch("/api/diagnostics")
        ]);

        if (healthRes.ok && diagRes.ok) {
            const health = await healthRes.json();
            const diag = await diagRes.json();

            const modeEl = document.getElementById("diag-bridge-mode");
            const subEl = document.getElementById("diag-bridge-sub");
            const memEl = document.getElementById("diag-memory");
            const targetsEl = document.getElementById("diag-targets-count");
            const rawDump = document.getElementById("raw-telemetry-json");
            const pillsContainer = document.getElementById("monitored-pills");

            if (modeEl) modeEl.textContent = health.mode;
            if (subEl) subEl.textContent = health.is_synthetic ? "Synthetic Brownian Replay" : "Windows Native MT5 Terminal";
            if (memEl) memEl.textContent = `${diag.process.memory_rss_mb} MB`;
            if (targetsEl) targetsEl.textContent = `${diag.monitored_targets_count} Pairs`;

            if (pillsContainer && health.active_targets) {
                pillsContainer.innerHTML = "";
                health.active_targets.forEach(t => {
                    const pill = document.createElement("span");
                    pill.className = "pill";
                    pill.textContent = `${t.symbol} [${t.timeframe}]`;
                    pillsContainer.appendChild(pill);
                });
            }

            if (rawDump) {
                rawDump.textContent = JSON.stringify({ health, diagnostics: diag }, null, 2);
            }
        }
    } catch (e) {
        console.error("Failed to fetch diagnostics:", e);
    }
}
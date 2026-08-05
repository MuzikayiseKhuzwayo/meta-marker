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
        title: "Indicator Matrix & Dynamic Scores",
        html: `
            <p><strong>Dynamic Reliability:</strong> Dynamic weights tracking the recent statistical win-rate accuracy of each specific indicator in the current market regime.</p>
        `
    }
};

async function initDashboard() {
    setupSelectors();
    setupChartInteractions();
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

// Setup drag and swipe interactions on the canvas
function setupChartInteractions() {
    const canvas = document.getElementById("price-chart");
    if (!canvas) return;

    const startDrag = (clientX) => {
        isDragging = true;
        dragStartX = clientX;
        canvas.style.cursor = "grabbing";
    };

    const moveDrag = (clientX) => {
        if (!isDragging || !chartData || !chartData.history) return;
        
        const deltaX = clientX - dragStartX;
        const widthPerCandle = canvas.width / visibleCandleCount;
        
        // Convert pixel drag movement to candle count index offset
        const indexShift = Math.round(deltaX / widthPerCandle);
        if (indexShift !== 0) {
            const historyLength = chartData.history.length;
            const maxScroll = Math.max(0, historyLength - visibleCandleCount);
            
            // Adjust scrollIndex (panning left adds to index, panning right subtracts)
            scrollIndex = Math.max(0, Math.min(maxScroll, scrollIndex - indexShift));
            dragStartX = clientX; // Anchor to new drag position for smoother tracking
            drawChart(chartData);
        }
    };

    const stopDrag = () => {
        isDragging = false;
        canvas.style.cursor = "crosshair";
    };

    // Mouse events
    canvas.addEventListener("mousedown", (e) => startDrag(e.clientX));
    canvas.addEventListener("mousemove", (e) => moveDrag(e.clientX));
    window.addEventListener("mouseup", stopDrag);
    canvas.addEventListener("mouseleave", stopDrag);

    // Touch events
    canvas.addEventListener("touchstart", (e) => {
        if (e.touches.length === 1) startDrag(e.touches[0].clientX);
    }, { passive: true });
    canvas.addEventListener("touchmove", (e) => {
        if (e.touches.length === 1) moveDrag(e.touches[0].clientX);
    }, { passive: true });
    canvas.addEventListener("touchend", stopDrag);
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
            const currentVal = symSelect.value;
            
            symSelect.innerHTML = "";
            const uniqueSymbols = [...new Set(targets.map(t => t.symbol))];
            uniqueSymbols.forEach(symbol => {
                const opt = document.createElement("option");
                opt.value = symbol;
                opt.textContent = symbol;
                symSelect.appendChild(opt);
            });
            if (uniqueSymbols.includes(currentVal)) {
                symSelect.value = currentVal;
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

    document.querySelectorAll(".info-trigger").forEach(btn => {
        btn.addEventListener("click", (e) => {
            e.stopPropagation();
            const topic = btn.getAttribute("data-topic");
            openModal(topic);
        });
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

    Object.keys(data.indicator_signals).forEach(key => {
        const sig = data.indicator_signals[key];
        const row = document.createElement("tr");

        let sigClass = "sig-neutral";
        if (sig.signal === "BUY") sigClass = "sig-buy";
        else if (sig.signal === "SELL") sigClass = "sig-sell";

        let displayVal = sig.value.toFixed(2);
        if (key === "Market_Structure") displayVal = "Aligned";

        row.innerHTML = `
            <td><strong>${sig.name.replace("_", " ")}</strong></td>
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
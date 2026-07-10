// Meta-Marker Front-End Dashboard logic

document.addEventListener("DOMContentLoaded", () => {
    initDashboard();
    initModalHandlers();
});

let statePollingInterval;

// Definitions mapping for explanation Modals
const TOPIC_EXPLANATIONS = {
    system: {
        title: "Meta-Marker Dashboard Overview",
        html: `
            <p>Welcome to the <strong>Meta-Marker Market Intelligence Dashboard</strong>.</p>
            <p>This analytics interface aggregates algorithmic telemetry, statistical classifications, and real-time technical indicators to provide concrete execution strategies for the M15 XAU/USD timeframe.</p>
            <p><strong>Workflow:</strong> Monitor the Market Classification to determine the trade posture, observe the Confidence Engine for operational convergence, and execute structural strategies via the Actionable Recommendation card.</p>
        `
    },
    classification: {
        title: "Market Classification",
        html: `
            <p>Classifying market structures assists in determining which algorithms should take dominance in the current setup.</p>
            <p><strong>Primary Regime:</strong> Displays whether the market is consolidating (mean-reverting), expanding structurally, or trending aggressively.</p>
            <p><strong>Trend Classification:</strong> Tracks micro-structures such as Higher Highs, Lower Lows, or structural breaks.</p>
            <p><strong>Volatility & Momentum:</strong> Monitors changes in current market standard deviation levels and real-time momentum velocity relative to baseline ranges.</p>
        `
    },
    confidence: {
        title: "Confidence Engine",
        html: `
            <p>The <strong>Confidence Engine</strong> compiles mathematical inputs across all sub-indicators and ranks active directional flow.</p>
            <p>The dial shows dynamic weighted results:
                <ul>
                    <li><strong>Buy Confidence (Green):</strong> Signal convergence favoring upward breakout vectors.</li>
                    <li><strong>Sell Confidence (Red):</strong> Signal convergence favoring downward breakout vectors.</li>
                    <li><strong>Neutral (Cyan):</strong> Contradicting indicators suggesting low probability conditions.</li>
                </ul>
            </p>
            <p>An execution bias occurs when any single direction exceeds a 60% threshold limit.</p>
        `
    },
    recommendation: {
        title: "Actionable Recommendation",
        html: `
            <p>The <strong>Actionable Recommendation</strong> is computed by an automated expert filter matrix.</p>
            <p>It processes underlying volatility, momentum ranges, and dynamic indicator weights to propose clear, systematic guidelines:</p>
            <p><strong>"BUY" or "SELL":</strong> Executes only when structural validation conditions align with strong dynamic reliability parameters.</p>
            <p><strong>"HOLD/WAIT":</strong> Enforces caution during high-volatility events, low liquidity times, or when indicator conflicts occur.</p>
        `
    },
    chart: {
        title: "Live Price Action Chart",
        html: `
            <p>This panel renders real-time structural candlestick history directly onto the interface canvas.</p>
            <p>The visual engine maps classic candlestick formations on the M15 timeframe, scaling prices with a percentage buffer dynamically.</p>
            <p>Bullish candles are highlighted in <strong>Cyan</strong>, and Bearish candles are displayed in <strong>Red</strong> to match system-wide color variables.</p>
        `
    },
    indicators: {
        title: "Indicator Matrix & Dynamic Scores",
        html: `
            <p>The <strong>Indicator Matrix</strong> exposes active calculations from localized sub-algorithms.</p>
            <p><strong>Value:</strong> Raw calculations from underlying momentum metrics, moving averages, and structural patterns.</p>
            <p><strong>Dynamic Reliability:</strong> Dynamic weights tracking the recent statistical win-rate accuracy of each specific indicator in the current market regime.</p>
        `
    }
};

function initDashboard() {
    fetchDashboardData();
    // Poll every 10 seconds for new updates
    statePollingInterval = setInterval(fetchDashboardData, 10000);
}

// Modal handling logic
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

    // Attach event listeners to every interactive info icon
    document.querySelectorAll(".info-trigger").forEach(btn => {
        btn.addEventListener("click", (e) => {
            e.stopPropagation();
            const topic = btn.getAttribute("data-topic");
            openModal(topic);
        });
    });

    // General system guide button at the top
    if (guideBtn) {
        guideBtn.addEventListener("click", () => {
            openModal("system");
        });
    }

    // Close on click close button, close on overlay background click
    if (closeBtn) {
        closeBtn.addEventListener("click", closeModal);
    }

    modal.addEventListener("click", (e) => {
        if (e.target === modal) {
            closeModal();
        }
    });

    // Close on ESC key press
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && modal.classList.contains("active")) {
            closeModal();
        }
    });
}

async function fetchDashboardData() {
    try {
        const response = await fetch("/api/state");
        if (!response.ok) {
            throw new Error("No data ingested yet.");
        }
        const data = await response.json();
        updateUI(data);
        drawChart(data);
    } catch (err) {
        console.error("Dashboard render error:", err);
        // Display the error on screen to diagnose the issue
        document.getElementById("recommendation-text").innerHTML = `
            <div style="font-size: 14px; color: var(--color-red); text-align: left; width: 100%;">
                <p><strong>Dashboard Error detected:</strong></p>
                <p style="margin-top: 4px; font-family: monospace; font-size: 12px; background: rgba(0,0,0,0.2); padding: 8px; border-radius: 6px; overflow-x: auto;">${err.stack || err.message}</p>
            </div>
        `;
    }
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
            <p><strong>Meta-Marker engine is running.</strong></p>
            <p style="margin-top: 8px; color: var(--text-secondary);">Please send M15 OHLC candle data via the MT5 EA or API endpoint <code>POST /api/candles</code> to initiate analysis.</p>
        </div>
    `;
}

function updateUI(data) {
    // 1. Regime Details
    document.getElementById("market-regime").textContent = data.classification.primary_regime.toUpperCase();
    document.getElementById("market-trend-state").textContent = data.classification.trend_state;
    document.getElementById("market-volatility").textContent = data.classification.volatility_state.toUpperCase();
    document.getElementById("market-momentum").textContent = data.classification.momentum_state.toUpperCase();

    // 2. Confidence Dials
    const buyConf = Math.round(data.confidence_buy);
    const sellConf = Math.round(data.confidence_sell);

    document.getElementById("buy-val").textContent = `${buyConf}%`;
    document.getElementById("sell-val").textContent = `${sellConf}%`;

    // Circle progress calc
    const circleFill = document.getElementById("buy-dial");
    const percentage = buyConf; // Scale dial to show buy strength
    const strokeOffset = 251 - (251 * percentage / 100);
    circleFill.style.strokeDashoffset = strokeOffset;

    // Dial display styling
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

    // 3. Recommendation Box
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

    // 4. Indicator Table Grid
    const tbody = document.getElementById("indicators-body");
    tbody.innerHTML = "";

    Object.keys(data.indicator_signals).forEach(key => {
        const sig = data.indicator_signals[key];
        const row = document.createElement("tr");

        let sigClass = "sig-neutral";
        if (sig.signal === "BUY") sigClass = "sig-buy";
        else if (sig.signal === "SELL") sigClass = "sig-sell";

        let displayVal = sig.value.toFixed(2);
        if (key === "Market_Structure") {
            displayVal = "Aligned";
        }

        row.innerHTML = `
            <td><strong>${sig.name.replace("_", " ")}</strong></td>
            <td><span class="sig-badge ${sigClass}">${sig.signal}</span></td>
            <td><code>${displayVal}</code></td>
            <td style="font-weight: 800; color: var(--color-cyan);">${Math.round(sig.confidence * 100)}%</td>
        `;
        tbody.appendChild(row);
    });
}

function drawChart(data) {
    const canvas = document.getElementById("price-chart");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    // Setup high DPI canvas
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width;
    canvas.height = rect.height;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const width = canvas.width;
    const height = canvas.height;

    const paddingLeft = 10;
    const paddingRight = 60; // Space for price labels on the right
    const paddingTop = 20;
    const paddingBottom = 20; // Space for time labels at the bottom

    const chartWidth = width - paddingLeft - paddingRight;
    const chartHeight = height - paddingTop - paddingBottom;

    const history = data.history || [];
    if (history.length === 0) {
        // Fallback: draw placeholder text
        ctx.fillStyle = "var(--text-secondary)";
        ctx.font = "14px Outfit, sans-serif";
        ctx.textAlign = "center";
        ctx.fillText("No chart history available yet", width / 2, height / 2);
        return;
    }

    // Find min and max prices to scale y-axis
    let minPrice = Math.min(...history.map(c => c.low));
    let maxPrice = Math.max(...history.map(c => c.high));

    // Add a small margin to top and bottom of chart scaling
    const priceRange = maxPrice - minPrice;
    const priceMargin = priceRange * 0.1 || 1.0;
    minPrice -= priceMargin;
    maxPrice += priceMargin;

    const scaleY = (price) => {
        return chartHeight - ((price - minPrice) / (maxPrice - minPrice)) * chartHeight + paddingTop;
    };

    // Draw background grid lines & Price Labels
    ctx.strokeStyle = "rgba(255, 255, 255, 0.03)";
    ctx.lineWidth = 1;
    ctx.fillStyle = "var(--text-secondary)";
    ctx.font = "10px Outfit, sans-serif";
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";

    const gridLinesCount = 5;
    for (let i = 0; i < gridLinesCount; i++) {
        const ratio = i / (gridLinesCount - 1);
        const price = maxPrice - ratio * (maxPrice - minPrice);
        const y = scaleY(price);

        // Horizontal Gridline
        ctx.beginPath();
        ctx.moveTo(paddingLeft, y);
        ctx.lineTo(paddingLeft + chartWidth, y);
        ctx.stroke();

        // Price Label on the right axis
        ctx.fillText(price.toFixed(2), paddingLeft + chartWidth + 8, y);
    }

    // Draw Candlesticks
    const candleWidth = chartWidth / history.length;
    const bodyPadding = Math.max(1, candleWidth * 0.2); // 20% padding between bodies

    history.forEach((candle, idx) => {
        const x = paddingLeft + idx * candleWidth + candleWidth / 2;

        const yOpen = scaleY(candle.open);
        const yClose = scaleY(candle.close);
        const yHigh = scaleY(candle.high);
        const yLow = scaleY(candle.low);

        const isBullish = candle.close >= candle.open;
        const color = isBullish ? "#05ffc5" : "#ff3b30"; // Green / Red

        ctx.strokeStyle = color;
        ctx.fillStyle = color;
        ctx.lineWidth = 1.5;

        // 1. Draw Wick (high to low)
        ctx.beginPath();
        ctx.moveTo(x, yHigh);
        ctx.lineTo(x, yLow);
        ctx.stroke();

        // 2. Draw Body (open to close)
        const bodyWidth = candleWidth - bodyPadding * 2;
        const bodyHeight = Math.max(1.5, Math.abs(yClose - yOpen));
        const bodyX = x - bodyWidth / 2;
        const bodyY = Math.min(yOpen, yClose);

        ctx.fillRect(bodyX, bodyY, bodyWidth, bodyHeight);

        // Draw Time labels at the bottom for every 8th candle
        if (idx % 8 === 0) {
            ctx.fillStyle = "var(--text-secondary)";
            ctx.textAlign = "center";
            ctx.textBaseline = "top";

            // Format time: HH:MM
            try {
                const date = new Date(candle.time);
                const hrs = String(date.getUTCHours()).padStart(2, '0');
                const mins = String(date.getUTCMinutes()).padStart(2, '0');
                ctx.fillText(`${hrs}:${mins}`, x, paddingBottom + chartHeight + 4);
            } catch (e) { }
        }
    });
}
import pytest
from fastapi.testclient import TestClient
from src.api.main import app
from src.engine.mt5_adapter import MT5Adapter, SyntheticMarketFeed

def test_synthetic_market_feed_generation():
    feed = SyntheticMarketFeed()
    rates = feed.get_or_generate_rates("XAUUSD", "M15", count=100)
    assert len(rates) == 100
    assert "time" in rates[0]
    assert "close" in rates[0]
    assert "open" in rates[0]
    assert "high" in rates[0]
    assert "low" in rates[0]
    assert rates[0]["high"] >= rates[0]["low"]

def test_adapter_initialization():
    adapter = MT5Adapter()
    assert adapter.initialize() is True
    symbols = adapter.symbols_get()
    assert len(symbols) > 0
    names = [s.name for s in symbols]
    assert "XAUUSD" in names
    adapter.shutdown()

def test_api_health_endpoint():
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "mode" in data
    assert "active_targets" in data

def test_api_diagnostics_endpoint():
    client = TestClient(app)
    response = client.get("/api/diagnostics")
    assert response.status_code == 200
    data = response.json()
    assert "engine_mode" in data
    assert "process" in data
    assert "monitored_targets_count" in data

def test_api_export_audit_csv():
    client = TestClient(app)
    response = client.get("/api/export/audit.csv")
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "id,symbol,timeframe" in response.text

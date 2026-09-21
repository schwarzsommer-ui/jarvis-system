def plan(symbol: str = "BTCUSD") -> dict:
    return {"workflow": "trading_monitor", "status": "simulated", "symbol": symbol, "advice": False}

import json
from datetime import datetime
import MetaTrader5 as mt5
from config import SYMBOL, ENTRY_TIMEFRAME, CANDLES, SIGNAL_FILE


def main():
    if not mt5.initialize():
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
    try:
        if not mt5.symbol_select(SYMBOL, True):
            raise RuntimeError(f"Cannot select {SYMBOL}")
        rates = mt5.copy_rates_from_pos(SYMBOL, ENTRY_TIMEFRAME, 0, CANDLES + 2)
        tick = mt5.symbol_info_tick(SYMBOL)
        info = mt5.symbol_info(SYMBOL)
        if rates is None or len(rates) < 30 or tick is None or info is None:
            raise RuntimeError(f"Insufficient market data: {mt5.last_error()}")

        # Exclude the currently forming M3 candle (index -1).
        completed = rates[:-1]
        candles = []
        for r in completed:
            candles.append({
                "time": datetime.fromtimestamp(int(r["time"])).strftime("%Y-%m-%d %H:%M:%S"),
                "open": float(r["open"]), "high": float(r["high"]),
                "low": float(r["low"]), "close": float(r["close"]),
                "tick_volume": int(r["tick_volume"]),
                "spread": int(r["spread"]),
            })
        payload = {
            "symbol": SYMBOL,
            "timeframe": "M3",
            "candles": candles,
            "latest_completed_m3": candles[-1]["time"],
            "live_bid": float(tick.bid),
            "live_ask": float(tick.ask),
            "live_spread_points": round((tick.ask - tick.bid) / (info.point or 1), 2),
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        with open("market_data.json", "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        print(f"M3 market data ready: {candles[-1]['time']}")
    finally:
        mt5.shutdown()

if __name__ == "__main__":
    main()

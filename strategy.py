import json
from datetime import datetime
from config import *


def rsi(values, period=14):
    if len(values) < period + 1:
        return 50.0
    gains = []
    losses = []
    for i in range(1, len(values)):
        d = values[i] - values[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    return 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))


def atr(candles, period=14):
    if len(candles) < period + 1:
        return 0.0
    tr = []
    for i in range(1, len(candles)):
        h = candles[i]["high"]; l = candles[i]["low"]; pc = candles[i-1]["close"]
        tr.append(max(h-l, abs(h-pc), abs(l-pc)))
    return sum(tr[-period:]) / period


def main():
    with open("market_data.json", "r", encoding="utf-8") as f:
        md = json.load(f)
    c = md["candles"]
    last = c[-1]
    closes = [x["close"] for x in c]
    a = atr(c, ATR_PERIOD)
    rv = rsi(closes, RSI_PERIOD)
    o, cl = last["open"], last["close"]
    if cl > o and rv > RSI_BUY_LEVEL:
        signal = "BUY"
        reason = "M3 GREEN + RSI > 50"
    elif cl < o and rv < RSI_SELL_LEVEL:
        signal = "SELL"
        reason = "M3 RED + RSI < 50"
    else:
        signal = "NO_TRADE"
        reason = "Doji or RSI confirmation failed"

    out = {
        "strategy_version": "M3-CANDLE-RSI14-FINAL",
        "symbol": SYMBOL,
        "timeframe": "M3",
        "signal": signal,
        "reason": reason,
        "candle_time": last["time"],
        "candle_open": o,
        "candle_close": cl,
        "rsi": round(rv, 4),
        "atr": round(a, 6),
        "price": cl,
        "stop_loss": None,
        "take_profit": None,
    }
    with open(SIGNAL_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print("=" * 70)
    print("M3 CANDLE + RSI SIGNAL")
    print("Signal:", signal, "| RSI:", round(rv, 2), "| ATR:", round(a, 4))
    print("Candle:", last["time"], "O:", o, "C:", cl)
    print("Reason:", reason)
    print("=" * 70)

if __name__ == "__main__":
    main()

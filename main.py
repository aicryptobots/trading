import subprocess, sys, time, json, os
from config import CHECK_INTERVAL, SIGNAL_FILE

print("="*70)
print("XAUUSDm M3 CANDLE + RSI 14 — FINAL")
print("="*70)

last_seen = None
while True:
    try:
        r = subprocess.run([sys.executable, "market_data.py"], check=False)
        if r.returncode != 0:
            time.sleep(CHECK_INTERVAL); continue
        with open("market_data.json","r",encoding="utf-8") as f: md=json.load(f)
        candle=md.get("latest_completed_m3")
        if candle == last_seen:
            # Still run trade manager so open positions are managed between candles.
            subprocess.run([sys.executable,"trade.py"], check=False)
            time.sleep(CHECK_INTERVAL); continue
        last_seen=candle
        subprocess.run([sys.executable,"strategy.py"], check=False)
        subprocess.run([sys.executable,"trade.py"], check=False)
    except KeyboardInterrupt:
        print("Stopped."); break
    except Exception as e:
        print("MAIN ERROR:", e)
    time.sleep(CHECK_INTERVAL)

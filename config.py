import MetaTrader5 as mt5

SYMBOL = "XAUUSDm"
ENTRY_TIMEFRAME = mt5.TIMEFRAME_M3
CANDLES = 300

LOT = 0.04
MIN_LOT = 0.01
MAX_LOT = 0.04
AUTO_LOT = False
RISK_PERCENT = 0.50

DEVIATION = 30
MAGIC_NUMBER = 20260903
CHECK_INTERVAL = 5
MAX_OPEN_TRADES = 1
MAX_TRADES_PER_DAY = 0          # 0 = unlimited
MAX_DAILY_LOSS_PERCENT = 0.0    # 0 = unlimited

RSI_PERIOD = 14
RSI_BUY_LEVEL = 50.0
RSI_SELL_LEVEL = 50.0
ATR_PERIOD = 14

SL_ATR = 0.60
TP_ATR = 0.35
MIN_RR = 0.35

# Profit booking from entry, as ATR multiples.
TP_STEP_1 = 0.20
TP_STEP_2 = 0.40
TP_STEP_3 = 0.60
TP_CLOSE_1 = 0.01
TP_CLOSE_2 = 0.01
TP_CLOSE_3 = 0.02

# If price moves 70% of the SL distance against the position,
# close 0.03 lot once. Remaining 0.01 lot stays protected by SL/TP.
ADVERSE_CLOSE_PERCENT = 50.0
ADVERSE_CLOSE_VOLUME = 0.03

BREAK_EVEN = False
TRAILING_STOP = False

MAX_SPREAD_POINTS = 350

SIGNAL_FILE = "signal.json"
STATE_FILE = "position_state.json"
LAST_CANDLE_FILE = "last_processed_m3.json"
TRADE_LOG_FILE = "trade_log.json"

ALARM_ENABLED = True
ALARM_FREQUENCY = 1200
ALARM_DURATION_MS = 300

print("=" * 70)
print("XAUUSDm M3 CANDLE + RSI 14 — FINAL")
print("=" * 70)
print("Entry Timeframe     : M3")
print("BUY Rule            : M3 GREEN + RSI > 50")
print("SELL Rule           : M3 RED + RSI < 50")
print("Doji                : NO TRADE")
print("Lot                 : 0.04")
print("Max Open Trades     : 1")
print("Daily Trades        : UNLIMITED")
print("Daily Loss          : UNLIMITED")
print("SL ATR              : 0.60")
print("TP ATR              : 0.35")
print("TP Steps            : 0.20 / 0.40 / 0.60")
print("Adverse Close       : 50.0% -> 0.03 lot")
print("Break Even          : OFF")
print("Trailing Stop       : OFF")
print("Filling Mode        : BROKER-AUTO")
print("=" * 70)

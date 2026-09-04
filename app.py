import json
import os
import re
import subprocess
import sys
import threading
from pathlib import Path
from datetime import datetime

from flask import Flask, jsonify, render_template, request

BASE = Path(__file__).resolve().parent
BOT_MAIN = BASE / "main.py"
CONFIG_FILE = BASE / "config.py"

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

_lock = threading.Lock()
_bot_process = None

EDITABLE = {
    "LOT": float,
    "MAX_OPEN_TRADES": int,
    "RSI_PERIOD": int,
    "RSI_BUY_LEVEL": float,
    "RSI_SELL_LEVEL": float,
    "ATR_PERIOD": int,
    "SL_ATR": float,
    "TP_ATR": float,
    "TP_STEP_1": float,
    "TP_STEP_2": float,
    "TP_STEP_3": float,
    "TP_CLOSE_1": float,
    "TP_CLOSE_2": float,
    "TP_CLOSE_3": float,
    "ADVERSE_CLOSE_PERCENT": float,
    "ADVERSE_CLOSE_VOLUME": float,
    "MAX_SPREAD_POINTS": float,
    "CHECK_INTERVAL": int,
}


def read_json(name, default=None):
    try:
        with open(BASE / name, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {} if default is None else default


def bot_running():
    global _bot_process
    with _lock:
        return bool(_bot_process and _bot_process.poll() is None)


def start_bot():
    global _bot_process
    with _lock:
        if _bot_process and _bot_process.poll() is None:
            return False, "Bot is already running"
        log = open(BASE / "bot_console.log", "a", encoding="utf-8", buffering=1)
        creationflags = 0
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        _bot_process = subprocess.Popen(
            [sys.executable, str(BOT_MAIN)],
            cwd=str(BASE),
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=creationflags,
        )
        return True, f"Bot started (PID {_bot_process.pid})"


def stop_bot():
    global _bot_process
    with _lock:
        if not _bot_process or _bot_process.poll() is not None:
            _bot_process = None
            return False, "Bot is not running"
        _bot_process.terminate()
        try:
            _bot_process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            _bot_process.kill()
        _bot_process = None
        return True, "Bot stopped"


def read_config_values():
    text = CONFIG_FILE.read_text(encoding="utf-8")
    out = {}
    for key, typ in EDITABLE.items():
        m = re.search(rf"^\s*{re.escape(key)}\s*=\s*([^#\r\n]+)", text, flags=re.M)
        if not m:
            continue
        raw = m.group(1).strip()
        try:
            out[key] = typ(raw)
        except Exception:
            out[key] = raw
    return out


def update_config_values(values):
    text = CONFIG_FILE.read_text(encoding="utf-8")
    changed = {}
    for key, typ in EDITABLE.items():
        if key not in values:
            continue
        try:
            val = typ(values[key])
        except Exception:
            raise ValueError(f"Invalid value for {key}")
        if key in {"LOT", "TP_CLOSE_1", "TP_CLOSE_2", "TP_CLOSE_3", "ADVERSE_CLOSE_VOLUME"} and val <= 0:
            raise ValueError(f"{key} must be greater than 0")
        if key in {"MAX_OPEN_TRADES", "RSI_PERIOD", "ATR_PERIOD", "CHECK_INTERVAL"} and val < 1:
            raise ValueError(f"{key} must be at least 1")
        if key == "ADVERSE_CLOSE_PERCENT" and not (0 < val <= 100):
            raise ValueError("ADVERSE_CLOSE_PERCENT must be between 0 and 100")
        rendered = str(int(val)) if typ is int else repr(float(val))
        pattern = rf"(^\s*{re.escape(key)}\s*=\s*)([^#\r\n]+)"
        text2, n = re.subn(pattern, rf"\g<1>{rendered}", text, count=1, flags=re.M)
        if n:
            text = text2
            changed[key] = val
    CONFIG_FILE.write_text(text, encoding="utf-8")
    return changed


def mt5_snapshot():
    try:
        import MetaTrader5 as mt5
    except Exception as e:
        return {"connected": False, "error": f"MetaTrader5 import failed: {e}"}
    try:
        if not mt5.initialize():
            return {"connected": False, "error": f"MT5 initialize failed: {mt5.last_error()}"}
        try:
            account = mt5.account_info()
            positions = mt5.positions_get(symbol="XAUUSDm") or []
            tick = mt5.symbol_info_tick("XAUUSDm")
            magic = 20260903
            mine = [p for p in positions if int(getattr(p, "magic", 0)) == magic]
            return {
                "connected": True,
                "account": None if not account else {
                    "login": int(account.login),
                    "balance": float(account.balance),
                    "equity": float(account.equity),
                    "margin": float(account.margin),
                    "free_margin": float(account.margin_free),
                    "profit": float(account.profit),
                    "currency": str(account.currency),
                },
                "tick": None if not tick else {"bid": float(tick.bid), "ask": float(tick.ask)},
                "positions": [
                    {
                        "ticket": int(p.ticket),
                        "type": "BUY" if p.type == mt5.POSITION_TYPE_BUY else "SELL",
                        "volume": float(p.volume),
                        "price_open": float(p.price_open),
                        "price_current": float(p.price_current),
                        "sl": float(p.sl),
                        "tp": float(p.tp),
                        "profit": float(p.profit),
                    }
                    for p in mine
                ],
            }
        finally:
            mt5.shutdown()
    except Exception as e:
        return {"connected": False, "error": str(e)}


def authorized():
    token = os.environ.get("WEB_API_TOKEN", "").strip()
    if not token:
        return True
    supplied = request.headers.get("X-API-Token", "")
    return supplied == token

def require_auth():
    if not authorized():
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    return None

@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/status")
def api_status():
    signal = read_json("signal.json")
    market = read_json("market_data.json")
    state = read_json("position_state.json")
    mt5 = mt5_snapshot()
    return jsonify({
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "bot_running": bot_running(),
        "signal": signal,
        "market": {
            "latest_completed_m3": market.get("latest_completed_m3"),
            "live_bid": market.get("live_bid"),
            "live_ask": market.get("live_ask"),
            "live_spread_points": market.get("live_spread_points"),
            "updated_at": market.get("updated_at"),
        },
        "position_state": state,
        "mt5": mt5,
    })


@app.get("/api/settings")
def api_settings():
    return jsonify(read_config_values())


@app.post("/api/settings")
def api_save_settings():
    denied = require_auth()
    if denied: return denied
    data = request.get_json(silent=True) or {}
    was_running = bot_running()
    if was_running:
        stop_bot()
    try:
        changed = update_config_values(data)
    except ValueError as e:
        if was_running:
            start_bot()
        return jsonify({"ok": False, "error": str(e)}), 400
    if was_running:
        start_bot()
    return jsonify({"ok": True, "changed": changed, "restarted": was_running})


@app.post("/api/bot/start")
def api_start():
    denied = require_auth()
    if denied: return denied
    ok, message = start_bot()
    return jsonify({"ok": ok, "message": message})


@app.post("/api/bot/stop")
def api_stop():
    denied = require_auth()
    if denied: return denied
    ok, message = stop_bot()
    return jsonify({"ok": ok, "message": message})


@app.post("/api/bot/restart")
def api_restart():
    denied = require_auth()
    if denied: return denied
    stop_bot()
    ok, message = start_bot()
    return jsonify({"ok": ok, "message": message})


@app.get("/api/log")
def api_log():
    path = BASE / "bot_console.log"
    if not path.exists():
        return jsonify({"log": ""})
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-120:]
        return jsonify({"log": "\n".join(lines)})
    except Exception as e:
        return jsonify({"log": f"Cannot read log: {e}"})


if __name__ == "__main__":
    host = os.environ.get("WEB_HOST", "127.0.0.1")
    port = int(os.environ.get("WEB_PORT", "5000"))
    app.run(host=host, port=port, debug=False, threaded=True)

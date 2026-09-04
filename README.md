# XAUUSDm Trading Bot — Professional Web Dashboard

Professional web control center for the existing **Python + MetaTrader 5 XAUUSDm M3 bot**.

## Architecture

- `app.py` — private Flask control/API server
- `templates/` + `static/` — full local control dashboard
- `main.py`, `strategy.py`, `trade.py`, `market_data.py` — trading engine
- `docs/` — optional GitHub Pages **read-only** monitoring page
- `config.py` — strategy configuration

## Run on Windows/VPS

1. Install Python and MetaTrader 5.
2. Log in to the correct MT5 account and enable Algo Trading as required.
3. Open a terminal in this folder.
4. Install dependencies: `python -m pip install -r requirements.txt`
5. Start dashboard: `python app.py`
6. Open `http://127.0.0.1:5000`
7. Start the bot from the dashboard.

The included `run_dashboard.bat` can automate the local startup.

## Remote/VPS security

The Flask server defaults to `127.0.0.1`. Do not expose it directly to the public Internet. If you put it behind a reverse proxy/VPN, set `WEB_API_TOKEN` on the server. Mutating endpoints (start/stop/restart/settings) then require the `X-API-Token` header.

**Never commit MT5 passwords, API keys, or live credentials to GitHub.**

## GitHub Pages

`docs/` is a public, read-only monitoring frontend. GitHub Pages cannot run Python/MT5. The trading engine must stay on a Windows PC/VPS. If you connect `docs/config.js` to a public API, keep that API read-only unless you have a proper authentication design.

## Existing strategy — unchanged

- Symbol: XAUUSDm
- Entry timeframe: M3
- BUY: completed green M3 candle + RSI > 50
- SELL: completed red M3 candle + RSI < 50
- Doji / failed RSI confirmation: no trade
- Lot: 0.04
- Max open trades: 1
- SL: 0.60 ATR
- TP: 0.35 ATR
- Profit steps: 0.20 / 0.40 / 0.60 ATR
- Partial closes: 0.01 / 0.01 / 0.02 lot
- Adverse protection: 50% of SL distance → close 0.03 lot once
- Break-even: OFF
- Trailing stop: OFF

### Important existing-rule note

The current strategy has TP at 0.35 ATR while profit steps 2 and 3 are at 0.40 and 0.60 ATR. This dashboard package intentionally does **not** alter that trading logic. Review that rule before live use.

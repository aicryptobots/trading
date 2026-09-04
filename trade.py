import json, os, math
from datetime import datetime
import MetaTrader5 as mt5
from config import *


def positions():
    ps = mt5.positions_get(symbol=SYMBOL) or []
    return [p for p in ps if int(getattr(p, "magic", 0)) == int(MAGIC_NUMBER)]


def normalize_volume(volume, info):
    step = float(info.volume_step or 0.01)
    vmin = float(info.volume_min or 0.01)
    vmax = float(info.volume_max or 100.0)
    volume = min(max(float(volume), vmin), vmax)
    steps = math.floor((volume + 1e-9) / step)
    return round(max(vmin, min(vmax, steps * step)), 8)


def supported_fillings(info):
    # SYMBOL_FILLING_FOK=1, IOC=2. RETURN is NOT a bit in filling_mode.
    flags = int(getattr(info, "filling_mode", 0) or 0)
    out = []
    if flags & 2:
        out.append(mt5.ORDER_FILLING_IOC)
    if flags & 1:
        out.append(mt5.ORDER_FILLING_FOK)
    # RETURN is valid except for Market Execution.
    if int(getattr(info, "trade_exemode", -1)) != int(getattr(mt5, "SYMBOL_TRADE_EXECUTION_MARKET", -999)):
        out.append(mt5.ORDER_FILLING_RETURN)
    # Last-resort modes only if not already present.
    for x in (mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_FOK):
        if x not in out:
            out.append(x)
    return out


def send_deal(order_type, volume, price, sl=0.0, tp=0.0, position_ticket=None, comment="M3 RSI"):
    info = mt5.symbol_info(SYMBOL)
    if not info:
        return None
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": SYMBOL,
        "volume": float(volume),
        "type": order_type,
        "price": float(price),
        "deviation": int(DEVIATION),
        "magic": int(MAGIC_NUMBER),
        "comment": comment,
    }
    if sl:
        request["sl"] = float(sl)
    if tp:
        request["tp"] = float(tp)
    if position_ticket is not None:
        request["position"] = int(position_ticket)

    last = None
    for fill in supported_fillings(info):
        request["type_filling"] = fill
        result = mt5.order_send(request)
        last = result
        if result and result.retcode in (mt5.TRADE_RETCODE_DONE, mt5.TRADE_RETCODE_DONE_PARTIAL):
            return result
        if result:
            print(f"FILLING {fill} rejected: retcode={result.retcode} comment={result.comment}")
    return last


def calc_atr_from_market():
    try:
        with open("market_data.json", "r", encoding="utf-8") as f:
            md = json.load(f)
        c = md["candles"]
        tr=[]
        for i in range(1, len(c)):
            h,l,pc=c[i]["high"],c[i]["low"],c[i-1]["close"]
            tr.append(max(h-l, abs(h-pc), abs(l-pc)))
        return sum(tr[-ATR_PERIOD:])/ATR_PERIOD
    except Exception:
        return 0.0


def trade_limits_ok():
    if MAX_TRADES_PER_DAY <= 0 and MAX_DAILY_LOSS_PERCENT <= 0:
        return True
    now = datetime.now()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    deals = mt5.history_deals_get(start, now) or []
    entries = [d for d in deals if int(getattr(d,"magic",0)) == MAGIC_NUMBER and int(getattr(d,"entry",-1)) == getattr(mt5,"DEAL_ENTRY_IN",0)]
    if MAX_TRADES_PER_DAY > 0 and len(entries) >= MAX_TRADES_PER_DAY:
        print("Daily trade limit reached")
        return False
    if MAX_DAILY_LOSS_PERCENT > 0:
        pnl = sum(float(getattr(d,"profit",0) or 0)+float(getattr(d,"commission",0) or 0)+float(getattr(d,"swap",0) or 0) for d in deals if int(getattr(d,"magic",0)) == MAGIC_NUMBER)
        acc = mt5.account_info()
        if acc and pnl <= -float(acc.balance)*MAX_DAILY_LOSS_PERCENT/100.0:
            print("Daily loss limit reached")
            return False
    return True


def open_trade(signal, atr_value):
    info = mt5.symbol_info(SYMBOL); tick = mt5.symbol_info_tick(SYMBOL)
    if not info or not tick:
        return None
    price = float(tick.ask if signal == "BUY" else tick.bid)
    distance_sl = max(atr_value * SL_ATR, float(info.trade_stops_level or 0) * info.point + 2*info.point)
    distance_tp = max(atr_value * TP_ATR, float(info.trade_stops_level or 0) * info.point + 2*info.point)
    sl = price - distance_sl if signal == "BUY" else price + distance_sl
    tp = price + distance_tp if signal == "BUY" else price - distance_tp
    sl = round(sl, info.digits); tp = round(tp, info.digits)
    volume = normalize_volume(LOT, info)
    typ = mt5.ORDER_TYPE_BUY if signal == "BUY" else mt5.ORDER_TYPE_SELL
    return send_deal(typ, volume, price, sl, tp, comment="M3 RSI ENTRY")


def load_state():
    if not os.path.exists(STATE_FILE): return {}
    try:
        with open(STATE_FILE,"r",encoding="utf-8") as f: return json.load(f)
    except Exception: return {}


def save_state(s):
    with open(STATE_FILE,"w",encoding="utf-8") as f: json.dump(s,f,indent=2)


def manage_position(p, atr_value):
    state = load_state()
    key = str(p.ticket)
    st = state.get(key)
    if not st:
        st = {"ticket": int(p.ticket), "initial_volume": float(p.volume), "entry": float(p.price_open), "direction": "BUY" if p.type == mt5.POSITION_TYPE_BUY else "SELL", "tp1": False, "tp2": False, "tp3": False, "adverse": False, "be": False}
        state[key] = st

    info = mt5.symbol_info(SYMBOL); tick = mt5.symbol_info_tick(SYMBOL)
    if not info or not tick: return
    direction = st["direction"]
    entry = float(st["entry"])
    current = float(tick.bid if direction == "BUY" else tick.ask)
    move = (current-entry) if direction == "BUY" else (entry-current)
    sl_dist = atr_value * SL_ATR

    # Profit protection: once price reaches +0.40 ATR, move SL to entry.
    # This protects a trade that first goes into profit and then reverses.
    if BREAK_EVEN and not st.get("be") and move >= atr_value * TP_STEP_1:
        new_sl = round(entry, info.digits)
        current_sl = float(getattr(p, "sl", 0.0) or 0.0)
        should_modify = (direction == "BUY" and (current_sl == 0.0 or new_sl > current_sl)) or (direction == "SELL" and (current_sl == 0.0 or new_sl < current_sl))
        if should_modify:
            req = {
                "action": mt5.TRADE_ACTION_SLTP,
                "symbol": SYMBOL,
                "position": int(p.ticket),
                "sl": new_sl,
                "tp": float(getattr(p, "tp", 0.0) or 0.0),
                "magic": int(MAGIC_NUMBER),
            }
            rbe = mt5.order_send(req)
            if rbe and rbe.retcode in (mt5.TRADE_RETCODE_DONE, mt5.TRADE_RETCODE_NO_CHANGES):
                st["be"] = True
                save_state(state)
                print(f"BREAK-EVEN: SL moved to entry {new_sl}")
        else:
            st["be"] = True
            save_state(state)

    # One-time adverse close: 50% of SL distance -> close 0.03 lot.
    if not st["adverse"] and move <= -(sl_dist * ADVERSE_CLOSE_PERCENT/100.0):
        close_vol = normalize_volume(min(ADVERSE_CLOSE_VOLUME, float(p.volume)), info)
        if close_vol > 0 and float(p.volume) - close_vol >= float(info.volume_min or 0.01) - 1e-9:
            typ = mt5.ORDER_TYPE_SELL if direction == "BUY" else mt5.ORDER_TYPE_BUY
            px = tick.bid if typ == mt5.ORDER_TYPE_SELL else tick.ask
            r = send_deal(typ, close_vol, px, position_ticket=p.ticket, comment="50% ADVERSE PARTIAL")
            if r and r.retcode in (mt5.TRADE_RETCODE_DONE, mt5.TRADE_RETCODE_DONE_PARTIAL):
                st["adverse"] = True
                save_state(state)
                print(f"PARTIAL ADVERSE CLOSE: {close_vol} lot | remaining managed")
                return

    # Profit steps. They are based on entry and current ATR snapshot.
    steps = [("tp1", TP_STEP_1, TP_CLOSE_1), ("tp2", TP_STEP_2, TP_CLOSE_2), ("tp3", TP_STEP_3, TP_CLOSE_3)]
    for flag, mult, vol_to_close in steps:
        if st.get(flag): continue
        if move >= atr_value * mult:
            close_vol = normalize_volume(min(vol_to_close, float(p.volume)), info)
            if close_vol <= 0: continue
            typ = mt5.ORDER_TYPE_SELL if direction == "BUY" else mt5.ORDER_TYPE_BUY
            px = tick.bid if typ == mt5.ORDER_TYPE_SELL else tick.ask
            r = send_deal(typ, close_vol, px, position_ticket=p.ticket, comment=f"{flag.upper()} PROFIT")
            if r and r.retcode in (mt5.TRADE_RETCODE_DONE, mt5.TRADE_RETCODE_DONE_PARTIAL):
                st[flag] = True
                save_state(state)
                print(f"{flag.upper()} PROFIT CLOSE: {close_vol} lot")
                return

    save_state(state)


def cleanup_state():
    state=load_state(); live={str(p.ticket) for p in positions()}
    changed=False
    for k in list(state):
        if k not in live:
            del state[k]; changed=True
    if changed: save_state(state)


def main():
    if not mt5.initialize(): raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
    try:
        mt5.symbol_select(SYMBOL, True)
        info=mt5.symbol_info(SYMBOL); tick=mt5.symbol_info_tick(SYMBOL)
        if not info or not tick: raise RuntimeError("No symbol/tick")
        ps=positions(); atr_value=calc_atr_from_market()
        cleanup_state()
        ps=positions()
        for p in ps:
            manage_position(p, atr_value)

        if not os.path.exists(SIGNAL_FILE): return
        with open(SIGNAL_FILE,"r",encoding="utf-8") as f: s=json.load(f)
        signal=s.get("signal"); candle=s.get("candle_time")
        if signal not in ("BUY","SELL"):
            print("NO_TRADE — no entry")
            return
        if ps:
            print("MAX_OPEN_TRADES reached — no new trade")
            return
        spread=(tick.ask-tick.bid)/(info.point or 1)
        if spread > MAX_SPREAD_POINTS:
            print(f"Spread too high: {spread:.1f} > {MAX_SPREAD_POINTS}")
            return
        if not trade_limits_ok(): return
        last=""
        if os.path.exists(LAST_CANDLE_FILE):
            try:
                with open(LAST_CANDLE_FILE,"r",encoding="utf-8") as f: last=json.load(f).get("candle_time","")
            except Exception: pass
        if candle == last:
            print("Same completed M3 candle already processed:", candle)
            return

        result=open_trade(signal, atr_value)
        if result and result.retcode in (mt5.TRADE_RETCODE_DONE, mt5.TRADE_RETCODE_DONE_PARTIAL):
            with open(LAST_CANDLE_FILE,"w",encoding="utf-8") as f: json.dump({"candle_time":candle,"order":int(result.order)},f,indent=2)
            print("="*70)
            print("ORDER OPENED", signal, "ticket/order:", result.order, "retcode:", result.retcode)
            print("="*70)
        else:
            print("ORDER FAILED", getattr(result,"retcode",None), getattr(result,"comment",""), mt5.last_error())
    finally:
        mt5.shutdown()

if __name__ == "__main__": main()

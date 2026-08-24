#!/usr/bin/env python3
"""
BTC Entry Signal Agent -- v4.1 (DXY Fix)
Uses FRED DTWEXM (Major Currencies) instead of DTWEXBGS.
Adds sanity check for stale DXY data.
"""

import requests
import os
from datetime import datetime, timezone

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
FRED_API_KEY = os.getenv("FRED_API_KEY")

def get(url, params=None):
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    return r.json()

def crypto():
    d = get("https://api.coingecko.com/api/v3/simple/price",
            {"ids":"bitcoin","vs_currencies":"usd","include_24hr_change":"true"})
    return {"btc": d["bitcoin"]["usd"], "btc_24h": d["bitcoin"]["usd_24h_change"]}

def crypto_history():
    d = get("https://api.coingecko.com/api/v3/coins/bitcoin/market_chart",
            {"vs_currency":"usd","days":"30","interval":"daily"})
    prices = [p[1] for p in d["prices"]]
    low7 = min(prices[-7:])
    low30 = min(prices[-30:])
    cur = prices[-1]
    return {"heat7": (cur/low7-1)*100, "heat30": (cur/low30-1)*100}

def get_fred(series):
    if not FRED_API_KEY:
        return None
    try:
        d = get("https://api.stlouisfed.org/fred/series/observations",
                {"series_id":series,"api_key":FRED_API_KEY,"file_type":"json","sort_order":"desc","limit":1})
        return float(d["observations"][0]["value"])
    except:
        return None

def assess(btc, btc24h, heat7, heat30, y10, dxy):
    kings = 0
    ctx = 0
    lines = []

    # KING 1: Heat
    if heat7 < 5:
        lines.append("HEAT: Safe -- +" + str(round(heat7,1)) + "% above 7d low")
        kings += 1
    elif heat7 < 15:
        lines.append("HEAT: Warm -- +" + str(round(heat7,1)) + "% above 7d low")
    else:
        lines.append("HEAT: Danger -- +" + str(round(heat7,1)) + "% above 7d low")

    # KING 2: 10Y yield
    if y10 is not None:
        if y10 < 3.5:
            lines.append("10Y: Falling -- " + str(round(y10,2)) + "%")
            kings += 1
        elif y10 < 4.5:
            lines.append("10Y: Elevated -- " + str(round(y10,2)) + "%")
        else:
            lines.append("10Y: Restrictive -- " + str(round(y10,2)) + "%")
    else:
        lines.append("10Y: No FRED key")

    # CONTEXT 1: DXY (with sanity check)
    if dxy is not None:
        if dxy > 110:
            lines.append("DXY: Stale data? -- " + str(round(dxy,1)) + " (check FRED series)")
        elif dxy < 100:
            lines.append("DXY: Tailwind -- " + str(round(dxy,1)))
            ctx += 1
        elif dxy < 104:
            lines.append("DXY: Neutral -- " + str(round(dxy,1)))
        else:
            lines.append("DXY: Headwind -- " + str(round(dxy,1)))
    else:
        lines.append("DXY: No FRED key")

    # CONTEXT 2: BTC 24h
    if btc24h < 5:
        lines.append("BTC: Calm -- 24h " + str(round(btc24h,1)) + "%")
        ctx += 1
    elif btc24h < 15:
        lines.append("BTC: Heating -- 24h " + str(round(btc24h,1)) + "%")
    else:
        lines.append("BTC: Chasing -- 24h " + str(round(btc24h,1)) + "%")

    # VERDICT
    if kings == 2 and ctx >= 1:
        verdict = "DEPLOY"
        action = "Buy $10k BTC now. Set limit at -5% ($" + str(round(btc*0.95)) + ")."
    elif kings == 2 and ctx == 0:
        verdict = "WATCH"
        action = "Kings aligned but momentum hot. Wait for a dip."
    elif kings == 1:
        verdict = "WAIT"
        action = "One king red. No deploy today. $30k stays parked."
    else:
        verdict = "DO NOT THINK ABOUT BTC TODAY"
        action = "Both kings red. Close the app. Go outside."

    return lines, verdict, action

def build(btc, heat7, heat30, lines, verdict, action):
    now = datetime.now(timezone.utc).strftime("%H:%M UTC %d %b")
    out = "BTC SIGNAL -- " + now + "\n\n"
    out += "BTC: $" + "{:,.0f}".format(btc) + "\n"
    out += "Heat: +" + str(round(heat7,1)) + "% above 7d low (30d: +" + str(round(heat30,1)) + "%)\n\n"
    out += "Signals:\n"
    for line in lines:
        out += line + "\n"
    out += "\nVERDICT: " + verdict + "\n" + action + "\n"
    if verdict == "WAIT" or verdict == "DO NOT THINK ABOUT BTC TODAY":
        out += "Your $30k stays in Binance. Metals untouched."
    return out

def send(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print(text)
        return
    r = requests.post("https://api.telegram.org/bot" + TELEGRAM_BOT_TOKEN + "/sendMessage",
        json={"chat_id":TELEGRAM_CHAT_ID,"text":text,"disable_web_page_preview":True},
        timeout=15)
    r.raise_for_status()

def main():
    c = crypto()
    h = crypto_history()
    y10 = get_fred("DGS10")
    dxy = get_fred("DTWEXM")  # Major currencies index (closer to ICE DXY)
    lines, verdict, action = assess(c["btc"], c["btc_24h"], h["heat7"], h["heat30"], y10, dxy)
    report = build(c["btc"], h["heat7"], h["heat30"], lines, verdict, action)
    send(report)
    print(verdict)

if __name__ == "__main__":
    main()

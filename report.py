#!/usr/bin/env python3
"""
BTC Entry Signal Agent — v3 (Money-Making Edition)
4 signals. 3 verdicts. Zero noise.
"""

import requests
import os
from datetime import datetime, timezone

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")

def get(url, params=None):
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    return r.json()

def crypto():
    d = get("https://api.coingecko.com/api/v3/simple/price",
            {"ids":"bitcoin,ethereum","vs_currencies":"usd","include_24hr_change":"true"})
    return {
        "btc": d["bitcoin"]["usd"],
        "btc_24h": d["bitcoin"]["usd_24h_change"],
    }

def binance():
    fr = get("https://fapi.binance.com/fapi/v1/premiumIndex?symbol=BTCUSDT")
    oi = get("https://fapi.binance.com/fapi/v1/openInterest?symbol=BTCUSDT")
    mp = float(fr["markPrice"])
    return {
        "funding": float(fr["lastFundingRate"]),
        "oi_usd": float(oi["openInterest"]) * mp,
    }

def yahoo(sym):
    d = get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}",
            {"interval":"1d","range":"1d"})
    m = d["chart"]["result"][0]["meta"]
    return float(m.get("regularMarketPrice") or m.get("previousClose") or m["chartPreviousClose"])

def assess(btc, btc_24h, funding, yield_10y, dxy):
    kings = 0
    ctx = 0
    lines = []

    if funding < 0.005:
        lines.append("🟢 FUNDING: Safe")
        kings += 1
    elif funding < 0.01:
        lines.append("🟡 FUNDING: Warm")
    else:
        lines.append("🔴 FUNDING: Danger — " + str(round(funding,4)))

    if yield_10y < 3.5:
        lines.append("🟢 10Y YIELD: Falling — " + str(round(yield_10y,2)) + "%")
        kings += 1
    elif yield_10y < 4.5:
        lines.append("🟡 10Y YIELD: Elevated — " + str(round(yield_10y,2)) + "%")
    else:
        lines.append("🔴 10Y YIELD: Restrictive — " + str(round(yield_10y,2)) + "%")

    if dxy < 100:
        lines.append("🟢 DXY: Tailwind — " + str(round(dxy,1)))
        ctx += 1
    elif dxy < 104:
        lines.append("🟡 DXY: Neutral — " + str(round(dxy,1)))
    else:
        lines.append("🔴 DXY: Headwind — " + str(round(dxy,1)))

    if btc_24h < 5:
        lines.append("🟢 BTC: Calm — 24h " + str(round(btc_24h,1)) + "%")
        ctx += 1
    elif btc_24h < 15:
        lines.append("🟡 BTC: Heating — 24h " + str(round(btc_24h,1)) + "%")
    else:
        lines.append("🔴 BTC: Chasing — 24h " + str(round(btc_24h,1)) + "%")

    if kings == 2 and ctx >= 1:
        verdict = "DEPLOY"
        action = "Buy $10k BTC now. Set limit at -5% ($" + str(round(btc*0.95)) + ")."
    elif kings == 2 and ctx == 0:
        verdict = "WATCH"
        action = "Kings aligned but momentum hot. Wait for a dip. Set alert at $" + str(round(btc*0.95)) + "."
    elif kings == 1:
        verdict = "WAIT"
        action = "One king red. No deploy today. $30k stays parked."
    else:
        verdict = "DO NOT THINK ABOUT BTC TODAY"
        action = "Both kings red. Close the app. Go outside."

    return lines, verdict, action

def build(btc, funding, oi, yield_10y, dxy, lines, verdict, action):
    now = datetime.now(timezone.utc).strftime("%H:%M UTC %d %b")
    out = [
        "📊 *BTC SIGNAL — " + now + "*",
        "",
        "*BTC*: $" + "{:,.0f}".format(btc),
        "*Funding*: " + str(round(funding,4)) + (" ⚠️" if funding > 0.02 else ""),
        "*OI*: $" + "{:.1f}".format(oi/1e9) + "B",
        "*10Y*: " + str(round(yield_10y,2)) + "%",
        "*DXY*: " + str(round(dxy,1)),
        "",
        "*Signals:*",
    ]
    out += lines
    out += [
        "",
        "🎯 *" + verdict + "*",
        action,
    ]
    if verdict == "WAIT" or verdict == "DO NOT THINK ABOUT BTC TODAY":
        out.append("💡 Your $30k stays in Binance. Metals untouched.")
    return "\n".join(out)

def send(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print(text)
        return
    r = requests.post(
        "https://api.telegram.org/bot" + TELEGRAM_BOT_TOKEN + "/sendMessage",
        json={"chat_id":TELEGRAM_CHAT_ID,"text":text,"parse_mode":"Markdown","disable_web_page_preview":True},
        timeout=15
    )
    r.raise_for_status()

def main():
    c = crypto()
    b = binance()
    y10 = yahoo("^TNX")
    dxy = yahoo("DX-Y.NYB")
    lines, verdict, action = assess(c["btc"], c["btc_24h"], b["funding"], y10, dxy)
    report = build(c["btc"], b["funding"], b["oi_usd"], y10, dxy, lines, verdict, action)
    send(report)
    print(verdict)

if __name__ == "__main__":
    main()

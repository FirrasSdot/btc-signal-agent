#!/usr/bin/env python3
"""
BTC Entry Signal Agent -- v7 (Final Working Version)
Tries OKX for funding rate (free, no key). Falls back to heat score if blocked.
Everything else: FRED (10Y, silver), exchangerate-api.com (EUR/USD), CoinGecko (BTC).
"""

import requests
import os
from datetime import datetime, timezone

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
FRED_API_KEY = os.getenv("FRED_API_KEY")

def get(url, params=None, headers=None):
    r = requests.get(url, params=params, headers=headers, timeout=15)
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

def get_funding():
    """Try OKX first (free, no key), then CoinGlass, then give up."""

    # Try OKX
    try:
        d = get("https://www.okx.com/api/v5/public/funding-rate", {"instId":"BTC-USDT-SWAP"})
        if "data" in d and len(d["data"]) > 0:
            return float(d["data"][0]["fundingRate"])
    except:
        pass

    # Try CoinGlass (no key needed for basic endpoints)
    try:
        d = get("https://api.coinglass.com/api/v1/fundingRate/history",
                {"symbol":"BTC","range":"1"})
        if "data" in d and len(d["data"]) > 0:
            return float(d["data"][0]["fundingRate"])
    except:
        pass

    return None

def get_fred(series):
    if not FRED_API_KEY:
        return None
    try:
        d = get("https://api.stlouisfed.org/fred/series/observations",
                {"series_id":series,"api_key":FRED_API_KEY,"file_type":"json","sort_order":"desc","limit":1})
        return float(d["observations"][0]["value"])
    except:
        return None

def get_eurusd():
    try:
        d = get("https://api.exchangerate-api.com/v4/latest/USD")
        return float(d["rates"]["EUR"])
    except:
        return None

def assess(btc, btc24h, funding, heat7, y10, eurusd, silver):
    kings = 0
    ctx = 0
    lines = []
    alerts = []
    funding_active = False

    # KING 1: Funding rate (if available) or Heat (fallback)
    if funding is not None:
        funding_active = True
        if funding < 0.005:
            lines.append("FUNDING: Safe -- " + str(round(funding,4)))
            kings += 1
        elif funding < 0.01:
            lines.append("FUNDING: Warm -- " + str(round(funding,4)))
        else:
            lines.append("FUNDING: Danger -- " + str(round(funding,4)))
    else:
        # Fallback to heat score
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

    # CONTEXT 1: Heat (always shown as context)
    if funding_active:
        if heat7 < 5:
            lines.append("MOMENTUM: Calm -- +" + str(round(heat7,1)) + "%")
            ctx += 1
        elif heat7 < 15:
            lines.append("MOMENTUM: Extended -- +" + str(round(heat7,1)) + "%")
        else:
            lines.append("MOMENTUM: Overbought -- +" + str(round(heat7,1)) + "%")

    # CONTEXT 2: DXY proxy
    if eurusd is not None:
        if eurusd > 1.08:
            lines.append("DXY: Tailwind (EUR/USD " + str(round(eurusd,4)) + ")")
            ctx += 1
        elif eurusd > 1.02:
            lines.append("DXY: Neutral (EUR/USD " + str(round(eurusd,4)) + ")")
        else:
            lines.append("DXY: Headwind (EUR/USD " + str(round(eurusd,4)) + ")")
    else:
        lines.append("DXY: EUR/USD fetch failed")

    # CONTEXT 3: BTC 24h
    if btc24h < 5:
        lines.append("BTC: Calm -- 24h " + str(round(btc24h,1)) + "%")
        ctx += 1
    elif btc24h < 15:
        lines.append("BTC: Heating -- 24h " + str(round(btc24h,1)) + "%")
    else:
        lines.append("BTC: Chasing -- 24h " + str(round(btc24h,1)) + "%")

    # SILVER ALERT
    if silver is not None:
        if silver >= 70:
            alerts.append("SILVER BREAKOUT: $" + str(round(silver,2)) + " >= $70! Metals bull broadening.")
        elif silver >= 65:
            alerts.append("SILVER WATCH: $" + str(round(silver,2)) + " -- approaching $70 breakout.")

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

    return lines, alerts, verdict, action, funding_active

def build(btc, funding, heat7, heat30, eurusd, silver, lines, alerts, verdict, action, funding_active):
    now = datetime.now(timezone.utc).strftime("%H:%M UTC %d %b")
    out = "BTC SIGNAL -- " + now + "\n\n"
    out += "BTC: $" + "{:,.0f}".format(btc) + "\n"
    if funding is not None:
        out += "Funding: " + str(round(funding,4)) + "\n"
    out += "Heat: +" + str(round(heat7,1)) + "% above 7d low (30d: +" + str(round(heat30,1)) + "%)\n"
    if eurusd is not None:
        out += "EUR/USD: " + str(round(eurusd,4)) + "\n"
    if silver is not None:
        out += "Silver: $" + str(round(silver,2)) + "\n"
    out += "\n"

    if alerts:
        out += "ALERTS:\n"
        for alert in alerts:
            out += alert + "\n"
        out += "\n"

    out += "Signals:\n"
    for line in lines:
        out += line + "\n"
    out += "\nVERDICT: " + verdict + "\n" + action + "\n"
    if verdict == "WAIT" or verdict == "DO NOT THINK ABOUT BTC TODAY":
        out += "Your $30k stays in Binance. Metals untouched."
    if not funding_active:
        out += "\n\nNote: Funding rate unavailable (OKX/CoinGlass blocked). Using heat score as proxy."
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
    funding = get_funding()
    y10 = get_fred("DGS10")
    eurusd = get_eurusd()
    silver = get_fred("SLVPRUSD")
    lines, alerts, verdict, action, funding_active = assess(c["btc"], c["btc_24h"], funding, h["heat7"], y10, eurusd, silver)
    report = build(c["btc"], funding, h["heat7"], h["heat30"], eurusd, silver, lines, alerts, verdict, action, funding_active)
    send(report)
    print(verdict)

if __name__ == "__main__":
    main()

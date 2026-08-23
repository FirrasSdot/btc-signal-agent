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
    # Current price + 24h change
    d = get("https://api.coingecko.com/api/v3/simple/price",
            {"ids":"bitcoin","vs_currencies":"usd","include_24hr_change":"true"})
    return {
        "btc": d["bitcoin"]["usd"],
        "btc_24h": d["bitcoin"]["usd_24h_change"],
    }

def crypto_history():
    # 30 days of daily prices to calculate "heat" (how extended from lows)
    d = get("https://api.coingecko.com/api/v3/coins/bitcoin/market_chart",
            {"vs_currency":"usd","days":"30","interval":"daily"})
    prices = [p[1] for p in d["prices"]]
    low_7d = min(prices[-7:])   # 7-day low
    low_30d = min(prices[-30:]) # 30-day low
    current = prices[-1]
    heat_7d = (current / low_7d - 1) * 100   # % above 7-day low
    heat_30d = (current / low_30d - 1) * 100  # % above 30-day low
    return {
        "heat_7d": heat_7d,
        "heat_30d": heat_30d,
        "low_7d": low_7d,
        "low_30d": low_30d,
    }

def yahoo(sym):
    d = get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}",
            {"interval":"1d","range":"1d"})
    m = d["chart"]["result"][0]["meta"]
    return float(m.get("regularMarketPrice") or m.get("previousClose") or m["chartPreviousClose"])

def assess(btc, btc_24h, heat_7d, heat_30d, yield_10y, dxy):
    kings = 0
    ctx = 0
    lines = []

    # KING 1: Heat score (proxy for funding rate / crowding)
    # < 5% above 7d low = calm (like funding < 0.005)
    # 5-15% = warm (like funding 0.005-0.01)
    # > 15% = danger (like funding > 0.01)
    if heat_7d < 5:
        lines.append("🟢 HEAT: Calm — +" + str(round(heat_7d,1)) + "% above 7d low")
        kings += 1
    elif heat_7d < 15:
        lines.append("🟡 HEAT: Warm — +" + str(round(heat_7d,1)) + "% above 7d low")
    else:
        lines.append("🔴 HEAT: Danger — +" + str(round(heat_7d,1)) + "% above 7d low")

    # KING 2: 10Y Yield
    if yield_10y < 3.5:
        lines.append("🟢 10Y YIELD: Falling — " + str(round(yield_10y,2)) + "%")
        kings += 1
    elif yield_10y < 4.5:
        lines.append("🟡 10Y YIELD: Elevated — " + str(round(yield_10y,2)) + "%")
    else:
        lines.append("🔴 10Y YIELD: Restrictive — " + str(round(yield_10y,2)) + "%")

    # CONTEXT 1: DXY
    if dxy < 100:
        lines.append("🟢 DXY: Tailwind — " + str(round(dxy,1)))
        ctx += 1
    elif dxy < 104:
        lines.append("🟡 DXY: Neutral — " + str(round(dxy,1)))
    else:
        lines.append("🔴 DXY: Headwind — " + str(round(dxy,1)))

    # CONTEXT 2: BTC 24h momentum
    if btc_24h < 5:
        lines.append("🟢 BTC: Calm — 24h " + str(round(btc_24h,1)) + "%")
        ctx += 1
    elif btc_24h < 15:
        lines.append("🟡 BTC: Heating — 24h " + str(round(btc_24h,1)) + "%")
    else:
        lines.append("🔴 BTC: Chasing — 24h " + str(round(btc_24h,1)) + "%")

    # VERDICT
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

def build(btc, heat_7d, heat_30d, yield_10y, dxy, lines, verdict, action):
    now = datetime.now(timezone.utc).strftime("%H:%M UTC %d %b")
    out = [
        "📊 *BTC SIGNAL — " + now + "*",
        "",
        "*BTC*: $" + "{:,.0f}".format(btc),
        "*Heat*: +" + str(round(heat_7d,1)) + "% above 7d low (30d: +" + str(round(heat_30d,1)) + "%)",
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
    return "
".join(out)

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
    h = crypto_history()
    y10 = yahoo("^TNX")
    dxy = yahoo("DX-Y.NYB")
    lines, verdict, action = assess(c["btc"], c["btc_24h"], h["heat_7d"], h["heat_30d"], y10, dxy)
    report = build(c["btc"], h["heat_7d"], h["heat_30d"], y10, dxy, lines, verdict, action)
    send(report)
    print(verdict)

if __name__ == "__main__":
    main()

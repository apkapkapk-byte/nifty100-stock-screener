import yfinance as yf
import pandas as pd
import yaml
import os
import requests
import io
from datetime import datetime

# ─── Load config ───────────────────────────────────────────────────────────────
with open("config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

# ─── Read MACD settings from config ────────────────────────────────────────────
# These are read once here and used inside the loop for every stock
# Defaults to industry standard values if not set in config
MACD_FAST   = config.get("macd_fast", 12)
MACD_SLOW   = config.get("macd_slow", 26)
MACD_SIGNAL = config.get("macd_signal", 9)
# ──────────────────────────────────────────────────────────────────────────────

# ─── Auto-fetch Nifty 100 tickers from NSE official CSV ───────────────────────

NSE_NIFTY100_URL = "https://nsearchives.nseindia.com/content/indices/ind_nifty100list.csv"

print(f"\n{'='*55}")
print(f"  NIFTY 100 STOCK SCREENER")
print(f"  Run at: {datetime.now().strftime('%d %b %Y, %I:%M %p')}")
print(f"{'='*55}\n")

print("Fetching Nifty 100 stock list from NSE...")
try:
    headers = {"User-Agent": "Mozilla/5.0"}  # NSE requires a browser-like header
    response = requests.get(NSE_NIFTY100_URL, headers=headers, timeout=10)
    nifty100_df = pd.read_csv(io.StringIO(response.text))
    # NSE CSV column is called 'Symbol' — we add .NS suffix for Yahoo Finance
    TICKERS = [symbol.strip() + ".NS" for symbol in nifty100_df["Symbol"].tolist()]
    print(f"  ✓ {len(TICKERS)} stocks loaded from NSE\n")
except Exception as e:
    print(f"  ✗ Could not fetch from NSE ({str(e)[:60]})")
    print(f"  Falling back to a hardcoded backup list...\n")
    # Fallback — top 20 Nifty 100 stocks in case NSE URL is temporarily unavailable
    TICKERS = [
        "RELIANCE.NS","TCS.NS","HDFCBANK.NS","BHARTIARTL.NS","ICICIBANK.NS",
        "INFOSYS.NS","SBIN.NS","HINDUNILVR.NS","ITC.NS","BAJFINANCE.NS",
        "KOTAKBANK.NS","LT.NS","HCLTECH.NS","MARUTI.NS","SUNPHARMA.NS",
        "ADANIENT.NS","ONGC.NS","NTPC.NS","TATAMOTORS.NS","AXISBANK.NS",
    ]
# ──────────────────────────────────────────────────────────────────────────────

# ─── DATA SOURCE ───────────────────────────────────────────────────────────────
# Currently using : Yahoo Finance (via yfinance library)
# Why             : Stable, free, accurate for end-of-day NSE data
# Future option   : NSE Official Bhavcopy CSV files (direct from NSE website)
# To switch later : Replace only the fetch loop below with an NSE CSV loader.
#                   Everything else (SMA calc, filters, Excel export) stays the same.
# ───────────────────────────────────────────────────────────────────────────────

# ─── Fetch data for each stock ─────────────────────────────────────────────────
print("Fetching price and fundamental data from Yahoo Finance...")
print("This may take 2-3 minutes for all 100 stocks...\n")

results = []

for ticker in TICKERS:
    try:
        stock = yf.Ticker(ticker)
        
        # Weekly historical data for 200W SMA (need ~200 weeks = ~4 years)
        hist = stock.history(period="5y", interval="1wk")
        if hist.empty or len(hist) < 50:
            continue

        current_price = hist["Close"].iloc[-1]
        sma_200w = hist["Close"].tail(200).mean()
        sma_pct = ((current_price - sma_200w) / sma_200w) * 100  # % above/below SMA

        # ── MACD Calculation ─────────────────────────────────────────────────
        # Uses daily price data — more granular than weekly, needed for MACD accuracy
        hist_daily = stock.history(period="1y", interval="1d")
        macd_line   = None
        signal_line = None
        macd_signal_label = None

        if not hist_daily.empty and len(hist_daily) >= MACD_SLOW:
            close = hist_daily["Close"]
            # EMA = Exponential Moving Average — gives more weight to recent prices
            ema_fast   = close.ewm(span=MACD_FAST, adjust=False).mean()
            ema_slow   = close.ewm(span=MACD_SLOW, adjust=False).mean()
            macd       = ema_fast - ema_slow
            signal     = macd.ewm(span=MACD_SIGNAL, adjust=False).mean()
            macd_line  = round(macd.iloc[-1], 4)
            signal_line= round(signal.iloc[-1], 4)
            # Crossover detection — did MACD cross above signal in last 3 days?
            recent_macd   = macd.iloc[-3:]
            recent_signal = signal.iloc[-3:]
            crossed_up = any(
                recent_macd.iloc[i] > recent_signal.iloc[i] and
                recent_macd.iloc[i-1] <= recent_signal.iloc[i-1]
                for i in range(1, len(recent_macd))
            )
            if macd_line > signal_line:
                macd_signal_label = "Bullish" + (" (crossover)" if crossed_up else "")
            elif macd_line < signal_line:
                macd_signal_label = "Bearish"
            else:
                macd_signal_label = "Neutral"
        # ─────────────────────────────────────────────────────────────────────

        # Fundamentals
        info = stock.info
        pe      = info.get("trailingPE", None)
        pb      = info.get("priceToBook", None)
        roe     = info.get("returnOnEquity", None)
        if roe: roe = roe * 100  # convert to %
        de      = info.get("debtToEquity", None)
        if de: de = de / 100     # yfinance gives it as %, normalize to ratio
        mktcap  = info.get("marketCap", None)
        if mktcap: mktcap = round(mktcap / 1e7, 0)  # convert to Cr
        current_ratio = info.get("currentRatio", None)  # cash & liquidity
        rev_growth = info.get("revenueGrowth", None)
        if rev_growth: rev_growth = rev_growth * 100
        eps     = info.get("trailingEps", None)
        div_yield = info.get("dividendYield", None)
        if div_yield: div_yield = div_yield * 100
        sector  = info.get("sector", "—")
        name    = info.get("shortName", ticker.replace(".NS",""))
        
        results.append({
            "Ticker":              ticker.replace(".NS",""),
            "Name":                name,
            "Sector":              sector,
            "Price (₹)":           round(current_price, 2),
            "200W SMA (₹)":        round(sma_200w, 2),
            "SMA % (above/below)": round(sma_pct, 2),
            "MACD Line":           macd_line,
            "Signal Line":         signal_line,
            "MACD Signal":         macd_signal_label,
            "P/E":                 round(pe, 2) if pe else None,
            "P/B":                 round(pb, 2) if pb else None,
            "ROE (%)":             round(roe, 2) if roe else None,
            "Debt/Equity":         round(de, 2) if de else None,
            "Current Ratio":       round(current_ratio, 2) if current_ratio else None,
            "Mkt Cap (₹ Cr)":      mktcap,
            "Rev Growth (%)":      round(rev_growth, 2) if rev_growth else None,
            "EPS (₹)":             round(eps, 2) if eps else None,
            "Div Yield (%)":       round(div_yield, 2) if div_yield else None,
        })
        print(f"  ✓ {ticker.replace('.NS',''):<15} | Price: ₹{current_price:>8.2f} | SMA%: {sma_pct:>+7.2f}%")

    except Exception as e:
        print(f"  ✗ {ticker.replace('.NS',''):<15} | Skipped ({str(e)[:40]})")
        continue

# ─── Apply config filters & rank ───────────────────────────────────────────────
print(f"\n{'-'*55}")
print(f"  Applying your config filters...\n")

df = pd.DataFrame(results)

# ─── Read filter settings from config ─────────────────────────────────────────
# Each line reads one setting from config.yaml
# If your friend hasn't set a filter, it defaults to None = filter is inactive
pe_max              = config.get("pe_max", None)
roe_min             = config.get("roe_min", None)
de_max              = config.get("debt_equity_max", None)
pb_max              = config.get("pb_max", None)
current_ratio_min   = config.get("current_ratio_min", None)
mktcap_min          = config.get("mktcap_min_cr", None)
mktcap_max          = config.get("mktcap_max_cr", None)
rev_growth_min      = config.get("rev_growth_min", None)
div_yield_min       = config.get("div_yield_min", None)
sector_exclude      = config.get("sector_exclude", [])
sector_include      = config.get("sector_include", [])
# ──────────────────────────────────────────────────────────────────────────────



# ─── Filter function for Sheet 2 ──────────────────────────────────────────────
# Takes one stock row, checks it against every active config filter
# Returns True if stock passes ALL filters, False if it fails any
def passes_filters(row):
    if pe_max and row.get("P/E") and row["P/E"] > pe_max:
        return False
    if roe_min and row.get("ROE (%)") and row["ROE (%)"] < roe_min:
        return False
    if de_max and row.get("Debt/Equity") and row["Debt/Equity"] > de_max:
        return False
    if pb_max and row.get("P/B") and row["P/B"] > pb_max:
        return False
    if current_ratio_min and row.get("Current Ratio") and row["Current Ratio"] < current_ratio_min:
        return False
    if mktcap_min and row.get("Mkt Cap (₹ Cr)") and row["Mkt Cap (₹ Cr)"] < mktcap_min:
        return False
    if mktcap_max and row.get("Mkt Cap (₹ Cr)") and row["Mkt Cap (₹ Cr)"] > mktcap_max:
        return False
    if rev_growth_min and row.get("Rev Growth (%)") and row["Rev Growth (%)"] < rev_growth_min:
        return False
    if div_yield_min and row.get("Div Yield (%)") and row["Div Yield (%)"] < div_yield_min:
        return False
    if sector_exclude and row.get("Sector") in sector_exclude:
        return False
    if sector_include and row.get("Sector") not in sector_include:
        return False
    return True
# ──────────────────────────────────────────────────────────────────────────────


# ascending=True means most negative % comes first — these are your reversal candidates
df = df.sort_values("SMA % (above/below)", ascending=True).reset_index(drop=True)
df.index = df.index + 1
df.index.name = "Rank"

# ─── Build filtered list for Sheet 2 ──────────────────────────────────────────
# Apply the filter function row by row across the full ranked dataframe
# df_filtered contains only stocks that passed ALL config filters
# It keeps the same SMA ranking order as the full list
df_filtered = df[df.apply(passes_filters, axis=1)].reset_index(drop=True)
df_filtered.index = df_filtered.index + 1
df_filtered.index.name = "Rank"
# ──────────────────────────────────────────────────────────────────────────────

# ─── Export to Excel — two sheets ─────────────────────────────────────────────
timestamp = datetime.now().strftime("%d%b%Y_%I%M%p")
filename = f"nifty100_screener_{timestamp}.xlsx"

with pd.ExcelWriter(filename, engine="openpyxl") as writer:

    # ── Sheet 1: Full List (all 200 stocks, sorted by SMA %) ──────────────────
    df.to_excel(writer, sheet_name="Full List", index=True)
    ws1 = writer.sheets["Full List"]
    ws1.insert_rows(1)
    ws1["A1"] = f"Full List — Nifty 100 | Run: {datetime.now().strftime('%d %b %Y, %I:%M %p')} | Ranked by 200W SMA — most underperforming first"
    for col in ws1.columns:
        max_len = max(len(str(cell.value)) if cell.value else 0 for cell in col) + 3
        ws1.column_dimensions[col[0].column_letter].width = min(max_len, 30)

    # ── Sheet 2: Filtered List (only stocks passing config filters) ───────────
    df_filtered.to_excel(writer, sheet_name="Filtered List", index=True)
    ws2 = writer.sheets["Filtered List"]
    ws2.insert_rows(1)
    ws2["A1"] = f"Filtered List — {len(df_filtered)} stocks passed config filters | Run: {datetime.now().strftime('%d %b %Y, %I:%M %p')}"
    for col in ws2.columns:
        max_len = max(len(str(cell.value)) if cell.value else 0 for cell in col) + 3
        ws2.column_dimensions[col[0].column_letter].width = min(max_len, 30)
# ──────────────────────────────────────────────────────────────────────────────

print(f"  Total stocks fetched:     {len(df)}")
print(f"  Stocks in filtered list:  {len(df_filtered)}")
print(f"\n  Output saved: {filename}")
print(f"  Sheet 1 → Full List ({len(df)} stocks)")
print(f"  Sheet 2 → Filtered List ({len(df_filtered)} stocks)")
print(f"{'='*55}\n")

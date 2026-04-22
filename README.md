# nifty100-stock-screener (made with claude)
Python stock screener for Nifty 100 using technical + fundamental indicators 
# Nifty 100 Stock Screener

A Python-based stock screener that analyzes Nifty 100 stocks using:

* Key technical indicators (200W SMA, MACD)
* Fundamental metrics (P/E, ROE, Debt/Equity, etc.)
* Custom filters via `config.yaml`

---

##  Features

* Auto-fetch Nifty 100 stocks from NSE
* Calculates SMA + MACD
* Applies user-defined filters
* Exports results to Excel

---

##  Tech Stack

* Python
* yfinance
* pandas
* openpyxl

---

## How to Run

```bash
pip install yfinance pandas openpyxl pyyaml
python screener.py
```

---

##  Output

* Excel file with:

  * Full List
  * Filtered List (based on user-defined filters)

---

##  Future Improvements

* Backtesting engine
* Portfolio optimization
* Strategy automation

## Bugs

* Passes unfit stocks to filtered list due to inadequate data availability of those stocks
* Analyses 93 out of 100 stocks with some errors and blank values, again due to data unavailability
* limitations due to data source-yahoo finance 

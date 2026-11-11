"""Read public financial statement facts from SEC EDGAR."""
from datetime import date

import requests

COMPANIES = {"HD": 354950, "WMT": 104169, "AAPL": 320193, "MSFT": 789019, "NVDA": 1045810}
METRICS = {
    "revenue": ("USD", ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet")),
    "netIncome": ("USD", ("NetIncomeLoss", "ProfitLoss")),
    "eps": ("USD/shares", ("EarningsPerShareDiluted",)),
}


def quarterly_facts(facts, unit, tags, today):
    periods = {}
    for tag in tags:
        for row in facts.get(tag, {}).get("units", {}).get(unit, []):
            if row["form"] != "10-Q" or not row.get("start") or row["filed"] > today.isoformat():
                continue
            duration = (date.fromisoformat(row["end"]) - date.fromisoformat(row["start"])).days
            if not 75 <= duration <= 105:
                continue
            end = row["end"]
            if end not in periods or row["filed"] > periods[end]["filed"]:
                periods[end] = row
    return periods


def company_fundamentals(fetch, today, previous):
    cached = {row["symbol"]: row for row in previous}
    companies = []
    for symbol, cik in COMPANIES.items():
        try:
            source = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
            payload = fetch(source, headers={"User-Agent": "Moomoo Market Calendar Demo (https://github.com/takayakato0519-spec/moomoo-market-calendar-demo/issues)"}).json()
            facts = payload["facts"]["us-gaap"]
            series = {name: quarterly_facts(facts, unit, tags, today)
                      for name, (unit, tags) in METRICS.items()}
            periods = sorted(series["revenue"], reverse=True)[:6]
            if not periods:
                raise ValueError("no quarterly revenue")
            rows = []
            for period in periods:
                filing = series["revenue"][period]
                accession = filing["accn"]
                rows.append(dict(period=period, filed=filing["filed"],
                    url=f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace('-', '')}/{accession}-index.html",
                    **{name: values.get(period, {}).get("val") for name, values in series.items()}))
            companies.append(dict(symbol=symbol, name=payload["entityName"], source=source, quarters=rows))
        except (requests.RequestException, ValueError, KeyError) as error:
            print(f"EDGAR {symbol}: {error}")
            if symbol in cached:
                companies.append(cached[symbol])
    return companies

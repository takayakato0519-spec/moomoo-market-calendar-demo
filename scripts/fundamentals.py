"""Read public financial statement facts from SEC EDGAR."""
from datetime import date, datetime
from io import BytesIO
import re
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader
from pypdf.errors import PdfReadError

COMPANIES = {"HD": 354950, "WMT": 104169, "AAPL": 320193, "MSFT": 789019, "NVDA": 1045810}
METRICS = {
    "revenue": ("USD", ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet")),
    "netIncome": ("USD", ("NetIncomeLoss", "ProfitLoss")),
    "eps": ("USD/shares", ("EarningsPerShareDiluted",)),
}

WALMART_IR = "https://stock.walmart.com/financial-information/financial-results"
HD_IR = "https://ir.homedepot.com/financial-reports/quarterly-earnings/"


def home_depot_filings(fetch, today):
    rows = []
    headers = {"User-Agent": "Mozilla/5.0"}
    for year in (today.year, today.year - 1):
        source = HD_IR + str(year)
        archive = BeautifulSoup(fetch(source, headers=headers).text, "html.parser")
        for link in archive.select("a[href]"):
            url = urljoin(source, link["href"])
            target = urlsplit(url)
            if target.scheme != "https" or target.hostname != "ir.homedepot.com":
                continue
            if not re.search(r"/hd-q[123]-\d{4}-10q\.pdf$", target.path, re.I):
                continue
            try:
                pdf = PdfReader(BytesIO(fetch(url, headers=headers).content))
                text = "\n".join(page.extract_text() for page in pdf.pages[:8])
                period = re.search(r"For the quarterly period ended\s+([A-Za-z]+ \d{1,2}, \d{4})", text, re.I)
                if not period:
                    continue
                end = datetime.strptime(period[1], "%B %d, %Y").date()
                values = {}
                for key, label, multiplier in (("revenue", "Net sales", 1_000_000),
                                                ("netIncome", "Net earnings", 1_000_000),
                                                ("eps", "Diluted earnings per share", 1)):
                    match = re.search(rf"^\s*{label}[ \t]+\$[ \t]*([\d,.]+)", text, re.M)
                    if match:
                        values[key] = float(match[1].replace(",", "")) * multiplier
                if end <= today and len(values) == 3:
                    rows.append(dict(period=end.isoformat(), url=url, **values))
            except (requests.RequestException, ValueError, PdfReadError) as error:
                print(f"Home Depot 10-Q: {error}")
    unique = {row["period"]: row for row in rows}
    return dict(symbol="HD", name="The Home Depot, Inc.", source=HD_IR + str(today.year),
                publisher="Home Depot公式IR", quarters=sorted(unique.values(), key=lambda row: row["period"], reverse=True)[:4])


def walmart_filings(fetch, today):
    index = BeautifulSoup(fetch(WALMART_IR).text, "html.parser")
    rows = []
    for link in index.select("a[href]"):
        url = link["href"]
        target = urlsplit(url)
        if target.scheme != "https" or target.hostname != "stock.walmart.com":
            continue
        match = re.fullmatch(r"/sec-filings/all-sec-filings/content/[\d-]+/wmt-(\d{4})(\d{2})(\d{2})\.htm", target.path)
        if not match or "10-Q" not in link.get_text(strip=True):
            continue
        period = "-".join(match.groups())
        if period > today.isoformat() or any(row["period"] == period for row in rows):
            continue
        page = BeautifulSoup(fetch(url).text, "html.parser")
        contexts = set()
        for context in page.find_all("xbrli:context"):
            end = context.find("xbrli:enddate")
            start = context.find("xbrli:startdate")
            if end and start and end.get_text(strip=True) == period and not context.find("xbrli:segment"):
                if 75 <= (date.fromisoformat(period) - date.fromisoformat(start.get_text(strip=True))).days <= 105:
                    contexts.add(context["id"])
        values = {}
        for name, (_, tags) in METRICS.items():
            for tag in tags:
                fact = page.find("ix:nonfraction", attrs={"name": f"us-gaap:{tag}", "contextref": list(contexts)})
                if fact:
                    try:
                        values[name] = float(fact.get_text(strip=True).replace(",", "")) * 10 ** int(fact.get("scale", 0))
                        if fact.get("sign") == "-":
                            values[name] *= -1
                    except ValueError:
                        continue
                    break
        if values:
            rows.append(dict(period=period, url=url, **values))
        if len(rows) >= 4:
            break
    return dict(symbol="WMT", name="Walmart Inc.", source=WALMART_IR, publisher="Walmart公式IR", quarters=rows)


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
            if symbol in ("HD", "WMT"):
                try:
                    provider = home_depot_filings if symbol == "HD" else walmart_filings
                    fallback = provider(fetch, today)
                    if fallback["quarters"]:
                        companies.append(fallback)
                        continue
                except (requests.RequestException, ValueError, KeyError) as fallback_error:
                    print(f"{symbol} IR filings: {fallback_error}")
            if symbol in cached:
                companies.append(cached[symbol])
    return companies

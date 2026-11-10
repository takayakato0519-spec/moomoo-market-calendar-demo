"""Update the public, read-only market calendar."""
import calendar
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
import re
from fractions import Fraction
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree
from urllib.parse import urlsplit
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

FRED = "https://fred.stlouisfed.org/releases/calendar"
NYSE = "https://www.nyse.com/trade/hours-calendars"
FINNHUB = "https://finnhub.io/api/v1/"
JST = ZoneInfo("Asia/Tokyo")
CENTRAL = ZoneInfo("America/Chicago")
RELEASES = {10: "消費者物価指数（CPI）", 46: "生産者物価指数（PPI）",
            50: "雇用統計", 53: "国内総生産（GDP）", 54: "個人所得・支出（PCE）",
            101: "FOMC声明", 192: "求人労働異動調査（JOLTS）"}
SYMBOLS = ("AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA")
OUT = Path(__file__).resolve().parents[1] / "data" / "calendar.js"


def fetch(url, **kwargs):
    response = requests.get(url, timeout=20, **kwargs)
    response.raise_for_status()
    return response


def economy(start, end):
    items = []
    for release_id, name in RELEASES.items():
        response = fetch(FRED, params={"rid": release_id, "view": "month",
                                        "vs": start.isoformat(), "ve": end.isoformat()})
        table = BeautifulSoup(response.text, "html.parser").select_one("#release-dates-pager table")
        if table is None:
            raise ValueError("FRED release table missing")
        current = None
        for row in table.select("tbody tr"):
            cells = row.find_all("td", recursive=False)
            if len(cells) == 1 and cells[0].find("span"):
                current = datetime.strptime(cells[0].span.get_text(strip=True), "%A %B %d, %Y").date()
                continue
            if len(cells) != 2 or current is None:
                continue
            link = cells[1].find("a", href=f"/release?rid={release_id}")
            if not link:
                continue
            stamp = cells[0].get_text(strip=True)
            local = current
            time = "時刻未定"
            if stamp:
                clock = datetime.strptime(stamp.upper(), "%I:%M %p").time()
                converted = datetime.combine(current, clock, CENTRAL).astimezone(JST)
                local, time = converted.date(), converted.strftime("%H:%M")
            items.append(dict(date=local.isoformat(), time=time, title=name, category="経済指標",
                              region="米国", detail="FRED公表カレンダー", url=urljoin(FRED, link["href"])))
    if not items:
        raise ValueError("No matching FRED releases")
    return items


def holidays(start, end):
    page = BeautifulSoup(fetch(NYSE).text, "html.parser")
    items = []
    for table in page.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue
        columns = [cell.get_text(" ", strip=True) for cell in rows[0].find_all(["th", "td"])]
        if sum(bool(re.fullmatch(r"20\d{2}", x)) for x in columns) < 2:
            continue
        for row in rows[1:]:
            cells = row.find_all(["th", "td"])
            for idx, year in enumerate(columns):
                if idx >= len(cells) or not re.fullmatch(r"20\d{2}", year):
                    continue
                match = re.search(r", ([A-Za-z]+) (\d{1,2})", cells[idx].get_text(" ", strip=True))
                if not match:
                    continue
                day = datetime.strptime(f"{year} {match[1]} {match[2]}", "%Y %B %d").date()
                if start <= day <= end:
                    items.append(dict(date=day.isoformat(), time="終日", title=cells[0].get_text(" ", strip=True),
                                      category="休場", region="NYSE", detail="取引所の現地日付", url=NYSE))
        return items
    raise ValueError("NYSE holiday table missing")


def licensed_data(start, end):
    key = os.environ["FINNHUB_API_KEY"]
    headers = {"X-Finnhub-Token": key}
    def get(endpoint, **params):
        return fetch(FINNHUB + endpoint, params=params, headers=headers).json()

    events = []
    for symbol in SYMBOLS:
        rows = get("calendar/earnings", symbol=symbol, **{"from": start.isoformat(), "to": end.isoformat()})
        for row in rows["earningsCalendar"]:
            events.append(dict(date=date.fromisoformat(row["date"]).isoformat(),
                               time={"bmo": "寄り前", "amc": "引け後"}.get(row.get("hour"), "時刻未定"),
                               title=symbol + " 決算予定", category="決算", region="米国",
                               detail="現地日付 · EPS予想 " + str(row["epsEstimate"]) if row.get("epsEstimate") is not None else "現地日付",
                               url="https://finnhub.io/docs/api/earnings-calendar"))
    trends = []
    for symbol in SYMBOLS:
        rows = get("stock/recommendation", symbol=symbol)
        if rows:
            row = max(rows, key=lambda item: item["period"])
            trends.append(dict(symbol=symbol, period=row["period"], **{
                field: int(row[field]) for field in ("strongBuy", "buy", "hold", "sell", "strongSell")
            }))
    return events, trends


def market_news():
    rss = "https://www.federalreserve.gov/feeds/press_monetary.xml"
    root = ElementTree.fromstring(fetch(rss).content)
    items = []
    for entry in root.findall("./channel/item"):
        url = entry.findtext("link", "").strip()
        target = urlsplit(url)
        if target.scheme != "https" or target.hostname != "www.federalreserve.gov":
            continue
        title = entry.findtext("title", "").strip()
        stamp = entry.findtext("pubDate", "").strip()
        if title and stamp:
            items.append(dict(title=title, url=url, date=parsedate_to_datetime(stamp).astimezone(JST).isoformat()))
    if not items:
        raise ValueError("No Federal Reserve news found")
    return sorted(items, key=lambda item: item["date"], reverse=True)[:8]


def issuer_earnings(today, end):
    url = "https://ir.homedepot.com/events-and-presentations"
    soup = BeautifulSoup(fetch(url, headers={"User-Agent": "Mozilla/5.0"}).text, "html.parser")
    section = soup.select_one(".upcoming-events-container")
    if section is None:
        if any("upcoming events" in h.get_text(strip=True).lower() for h in soup.find_all("h2")):
            return []
        raise ValueError("Home Depot IR events section missing")
    items = []
    for item in section.select(".upcoming-event-item"):
        title = item.select_one(".event-title")
        if title is None or "earnings release" not in title.get_text(strip=True).lower():
            continue
        stamp = item.select_one(".event-date-simple")
        if stamp is None:
            raise ValueError("Home Depot IR earnings date missing")
        local = datetime.strptime(" ".join(stamp.get_text().split()).upper(), "%A, %B %d, %Y %I:%M %p ET")
        if today <= local.date() <= end:
            items.append(dict(date=local.date().isoformat(), time=local.strftime("%H:%M") + " ET",
                              title="HD 決算発表", category="決算", region="米国",
                              detail="Home Depot公式IR · 取引所の現地日付", url=url))
    return items


def walmart_earnings(today, end):
    root = "https://corporate.walmart.com"
    soup = BeautifulSoup(fetch(root + "/news/events").text, "html.parser")
    cards = soup.select(".CorporateEvent-item")
    if not cards:
        raise ValueError("Walmart IR event cards missing")
    items = []
    for card in cards:
        link = card.select_one('.CorporateEvent-item-title a.Link[href^="/news/events/"][href$="-earnings-release"]')
        if not link:
            continue
        info = card.select_one(".CorporateEvent-item-date")
        if info is None:
            raise ValueError("Walmart IR event details missing")
        raw = " ".join(info.get_text(" ", strip=True).split())
        date_text, _, _ = raw.partition("|")
        local = datetime.strptime(date_text.strip().replace(".", ""), "%b %d, %Y").date()
        if today <= local <= end:
            items.append(dict(date=local.isoformat(), time="", title="WMT " + link.get_text(strip=True),
                              category="決算", region="米国",
                              detail="Walmart公式IR · " + raw.split("|", 1)[-1].strip().split("US/Central")[0].strip() + " CT（公式イベント時刻）",
                              url=root + link["href"]))
    return items


def attach_fomc_results(events, news, start):
    for item in news:
        if not re.fullmatch(r"https://www\.federalreserve\.gov/newsevents/pressreleases/monetary\d{8}a\.htm", item["url"]):
            continue
        if item["title"].casefold() != "federal reserve issues fomc statement":
            continue
        stamp = datetime.fromisoformat(item["date"])
        day = stamp.date().isoformat()
        if stamp.date() < start:
            continue
        event = next((e for e in events if e["title"] == RELEASES[101] and e["date"] == day), None)
        if event is None:
            event = dict(date=day, time=stamp.strftime("%H:%M"), title=RELEASES[101],
                         category="経済指標", region="米国", detail="FRB公式発表", url=item["url"])
            events.append(event)
        summary = "FOMC声明が公表されました。"
        try:
            page = BeautifulSoup(fetch(item["url"]).text, "html.parser")
            body = " ".join(page.get_text(" ", strip=True).split())
            match = re.search(r"target range for the federal funds rate (?:at|to) ([\d.]+(?:-\d+/\d+)?)\s*(?:to|[–-])\s*([\d.]+(?:-\d+/\d+)?)\s*percent", body, re.I)
            if match:
                def rate(value):
                    whole, separator, fraction = value.partition("-")
                    return float(whole) + (float(Fraction(fraction)) if separator else 0)
                summary = f"政策金利の誘導目標：{rate(match[1]):g}〜{rate(match[2]):g}％"
        except requests.RequestException:
            pass
        event["result"] = dict(url=item["url"], publishedAt=item["date"], summary=summary)


def attach_bls_results(events, now):
    series = {}
    for code in ("CUSR0000SA0", "CUUR0000SA0", "CES0000000001", "LNS14000000"):
        try:
            payload = fetch(f"https://api.bls.gov/publicAPI/v2/timeseries/data/{code}").json()
            rows = payload["Results"]["series"][0]["data"]
            series[code] = {(int(row["year"]), int(row["period"][1:])): float(row["value"])
                            for row in rows if row["period"] != "M13" and row["value"] not in ("", "-")}
        except (requests.RequestException, ValueError, KeyError, IndexError) as error:
            print(f"BLS {code}: {error}")
    for event in events:
        if event["title"] not in (RELEASES[10], RELEASES[50]) or not re.fullmatch(r"\d{2}:\d{2}", event["time"]):
            continue
        stamp = datetime.fromisoformat(event["date"] + "T" + event["time"]).replace(tzinfo=JST)
        if stamp > now:
            continue
        day = stamp.astimezone(ZoneInfo("America/New_York")).date()
        period = day.replace(day=1) - timedelta(days=1)
        previous = period.replace(day=1) - timedelta(days=1)
        def value(code, year, month):
            return series[code][year, month]
        try:
            if event["title"] == RELEASES[10]:
                adjusted = value("CUSR0000SA0", period.year, period.month)
                prior = value("CUSR0000SA0", previous.year, previous.month)
                raw = value("CUUR0000SA0", period.year, period.month)
                year_ago = series.get("CUUR0000SA0", {}).get((period.year - 1, period.month))
                summary = f"CPI 前月比 {(adjusted / prior - 1) * 100:+.1f}％（季節調整済み）"
                summary += f"・前年比 {(raw / year_ago - 1) * 100:+.1f}％" if year_ago else "・前年比は比較元の値なし"
                release = "cpi"
            else:
                jobs = value("CES0000000001", period.year, period.month) - value("CES0000000001", previous.year, previous.month)
                rate = value("LNS14000000", period.year, period.month)
                summary = f"非農業部門雇用者数 前月比 {jobs * 1000:+,.0f}人・失業率 {rate:.1f}％"
                release = "empsit"
        except (KeyError, ZeroDivisionError):
            continue
        event["result"] = dict(
            url=f"https://www.bls.gov/news.release/archives/{release}_{day:%m%d%Y}.htm",
            publishedAt=stamp.isoformat(),
            summary=f"{period.year}年{period.month}月分 · {summary}（BLS最新系列から計算、改定を含む）",
        )


def attach_earnings_results(events, now):
    first_day = (now.date() - timedelta(days=105))
    sources = {}
    try:
        for year in range(first_day.year, now.year + 1):
            origin = "https://ir.homedepot.com"
            archive = BeautifulSoup(fetch(f"{origin}/news-releases/{year}", headers={"User-Agent": "Mozilla/5.0"}).text, "html.parser")
            for link in archive.select('a[href^="/news-releases/"]'):
                match = re.fullmatch(r"/news-releases/\d{4}/(\d{2}-\d{2}-\d{4})-\d+", link["href"])
                if match and re.search(r"quarter fiscal .* results", link.get_text(" ", strip=True), re.I):
                    day = datetime.strptime(match[1], "%m-%d-%Y").date()
                    sources["HD", day] = origin + link["href"]
    except (requests.RequestException, ValueError) as error:
        print(f"HD results archive: {error}")
    try:
        for event in walmart_earnings(first_day, now.date()):
            page = BeautifulSoup(fetch(event["url"]).text, "html.parser")
            for link in page.select('a[href^="https://corporate.walmart.com/news/"]'):
                if re.search(r"/walmart-releases-.*-earnings$", link["href"]):
                    sources["WMT", date.fromisoformat(event["date"])] = link["href"]
                    break
    except (requests.RequestException, ValueError) as error:
        print(f"WMT results archive: {error}")
    for (symbol, day), url in sources.items():
        if not first_day <= day <= now.date():
            continue
        try:
            page = BeautifulSoup(fetch(url, headers={"User-Agent": "Mozilla/5.0"}).text, "html.parser")
        except requests.RequestException as error:
            print(f"{symbol} results for {day}: {error}")
            continue
        body = " ".join(page.stripped_strings)
        facts = []
        if symbol == "HD":
            sales = re.search(r"reported sales of \$([\d.]+) billion", body, re.I)
            eps = re.search(r"or \$([\d.]+) per diluted share", body, re.I)
            if sales:
                facts.append(f"売上高 {float(sales[1]) * 10:g}億ドル")
            if eps:
                facts.append(f"希薄化後EPS {eps[1]}ドル")
        else:
            growth = re.search(r"Total revenues\s+Q\d FY\d+\s+([\d.]+)%", body)
            if growth:
                facts.append(f"総収益 前年同期比 +{growth[1]}％")
        key = day.isoformat()
        event = next((row for row in events if row["date"] == key
                      and row["category"] == "決算" and row["title"].startswith(symbol + " ")), None)
        if event is None:
            event = dict(date=key, time="", title=f"{symbol} 決算発表",
                         category="決算", region="米国", detail="企業公式IR", url=url)
            events.append(event)
        event["result"] = dict(url=url, publishedAt=key,
                               summary="・".join(facts) if facts else "企業が決算結果を公表しました。")


def main():
    now = datetime.now(JST)
    start = now.date().replace(day=1)
    next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
    end = next_month.replace(day=calendar.monthrange(next_month.year, next_month.month)[1])
    events = economy(start - timedelta(days=1), end) + holidays(start, end)
    issuer_status = {}
    for symbol, source in {"HD": issuer_earnings, "WMT": walmart_earnings}.items():
        try:
            rows = source(now.astimezone(ZoneInfo("America/New_York")).date(), end)
            events.extend(rows)
            issuer_status[symbol] = len(rows)
        except (requests.RequestException, ValueError) as error:
            print(f"{symbol} IR unavailable: {type(error).__name__}: {error}")
            issuer_status[symbol] = None
    trends = []
    enabled = os.getenv("ENABLE_LICENSED_DATA") == "true"
    if enabled:
        private_events, trends = licensed_data(start, end)
        events.extend(private_events)
    attach_bls_results(events, now)
    news = market_news()
    result_start = (start - timedelta(days=1)).replace(day=1)
    attach_fomc_results(events, news, result_start)
    attach_earnings_results(events, now)
    payload = dict(updatedAt=now.isoformat(timespec="seconds"), coverage=[start.isoformat(), end.isoformat()],
                   events=sorted((e for e in events if (start.isoformat() <= e["date"] <= end.isoformat()) or e.get("result")),
                                 key=lambda e: (e["date"], e["time"], e["title"])),
                   analystTrends=trends, news=news, licensedData=enabled, issuerStatus=issuer_status)
    temp = OUT.with_suffix(".tmp")
    temp.write_text("window.MARKET_CALENDAR = " + json.dumps(payload, ensure_ascii=False, indent=2) + ";\n", encoding="utf-8")
    temp.replace(OUT)
    print(f"Updated {len(payload['events'])} events")


if __name__ == "__main__":
    main()

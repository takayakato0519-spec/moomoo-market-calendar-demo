"""Update the public, read-only market calendar."""
import calendar
import csv
from io import StringIO
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
from fundamentals import company_fundamentals
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


def nvidia_earnings(today, end):
    root = "https://nvidianews.nvidia.com"
    index = BeautifulSoup(fetch(root + "/news/latest").text, "html.parser")
    links = dict.fromkeys(a["href"] for a in index.select('a[href^="/news/nvidia-sets-conference-call-for-"]'))
    items = []
    for path in links:
        if "financial-results" not in path:
            continue
        url = root + path
        article = BeautifulSoup(fetch(url).text, "html.parser")
        published = article.select_one(".article-date")
        announcement = re.search(
            r"on [A-Za-z]+, ([A-Za-z]+ [0-9]{1,2}), at ([0-9]{1,2}(?::[0-9]{2})?) ([ap])[.]m[.]\s+PT",
            article.get_text(" ", strip=True))
        if published is None or announcement is None:
            continue
        published_date = datetime.strptime(published.get_text(strip=True), "%B %d, %Y").date()
        local = datetime.strptime(f"{announcement[1]}, {published_date.year}", "%B %d, %Y").date()
        if local < published_date:
            local = local.replace(year=local.year + 1)
        if today <= local <= end:
            raw_time = announcement[2] if ":" in announcement[2] else announcement[2] + ":00"
            call_time = datetime.strptime(raw_time + announcement[3].upper() + "M", "%I:%M%p")
            items.append(dict(date=local.isoformat(), time=call_time.strftime("%H:%M") + " PT",
                              title="NVDA 決算説明会", category="決算", region="米国",
                              detail="NVIDIA公式発表 · 説明会の現地時刻", url=url))
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


def payroll_at_release(day, period, previous):
    """Read BLS payroll levels as published on the release date via ALFRED."""
    try:
        response = fetch("https://alfred.stlouisfed.org/graph/alfredgraph.csv",
                         params={"id": "PAYEMS", "vintage_date": day.isoformat(),
                                 "cosd": previous.replace(day=1).isoformat(),
                                 "coed": period.replace(day=1).isoformat()})
        column = f"PAYEMS_{day:%Y%m%d}"
        levels = {row["observation_date"]: int(row[column])
                  for row in csv.DictReader(StringIO(response.text)) if row[column] not in ("", ".")}
        return (levels[period.replace(day=1).isoformat()]
                - levels[previous.replace(day=1).isoformat()]) * 1000
    except (requests.RequestException, ValueError, KeyError) as error:
        print(f"ALFRED payroll vintage {day}: {error}")
        return None


def attach_bls_results(events, now):
    series = {}
    for code in ("CUSR0000SA0", "CUUR0000SA0", "CES0000000001", "LNS14000000", "WPSFD4"):
        try:
            payload = fetch(f"https://api.bls.gov/publicAPI/v2/timeseries/data/{code}").json()
            rows = payload["Results"]["series"][0]["data"]
            series[code] = {(int(row["year"]), int(row["period"][1:])): float(row["value"])
                            for row in rows if row["period"] != "M13" and row["value"] not in ("", "-")}
        except (requests.RequestException, ValueError, KeyError, IndexError) as error:
            print(f"BLS {code}: {error}")
    if "WPSFD4" not in series:
        try:
            response = fetch("https://fred.stlouisfed.org/graph/fredgraph.csv",
                             params={"id": "PPIFIS", "cosd": f"{now.year - 1}-01-01"})
            series["WPSFD4"] = {(int(row["observation_date"][:4]), int(row["observation_date"][5:7])):
                               float(row["PPIFIS"]) for row in csv.DictReader(StringIO(response.text))
                               if row.get("PPIFIS") not in (None, "", ".")}
        except (requests.RequestException, KeyError, ValueError) as error:
            print(f"PPI mirror: {error}")
    for event in events:
        if event["title"] not in (RELEASES[10], RELEASES[46], RELEASES[50]) or not re.fullmatch(r"\d{2}:\d{2}", event["time"]):
            continue
        stamp = datetime.fromisoformat(event["date"] + "T" + event["time"]).replace(tzinfo=JST)
        if stamp > now:
            continue
        day = stamp.astimezone(ZoneInfo("America/New_York")).date()
        period = day.replace(day=1) - timedelta(days=1)
        previous = period.replace(day=1) - timedelta(days=1)
        def value(code, year, month):
            return series[code][year, month]
        metrics = []
        try:
            if event["title"] == RELEASES[10]:
                adjusted = value("CUSR0000SA0", period.year, period.month)
                prior = value("CUSR0000SA0", previous.year, previous.month)
                raw = value("CUUR0000SA0", period.year, period.month)
                year_ago = series.get("CUUR0000SA0", {}).get((period.year - 1, period.month))
                adjusted_series = series["CUSR0000SA0"]
                raw_series = series["CUUR0000SA0"]
                earlier = previous.replace(day=1) - timedelta(days=1)
                older = adjusted_series.get((earlier.year, earlier.month))
                prior_raw = raw_series.get((previous.year, previous.month))
                prior_year_ago = raw_series.get((previous.year - 1, previous.month))
                metrics = [
                    dict(label="CPI 前月比（季節調整済み）",
                         current=f"{(adjusted / prior - 1) * 100:+.1f}%",
                         previous=f"{(prior / older - 1) * 100:+.1f}%" if older else None),
                    dict(label="CPI 前年同月比",
                         current=f"{(raw / year_ago - 1) * 100:+.1f}%" if year_ago else None,
                         previous=f"{(prior_raw / prior_year_ago - 1) * 100:+.1f}%"
                         if prior_raw is not None and prior_year_ago else None),
                ]
                summary = "総合CPI"
                if not year_ago:
                    summary += ("・前年同月比は2025年10月の指数が未公表のため算出不可"
                                if (period.year, period.month) == (2026, 10)
                                else "・前年同月比は比較元の値を取得できませんでした")
                release = "cpi"
            elif event["title"] == RELEASES[46]:
                values = series["WPSFD4"]
                earlier = previous.replace(day=1) - timedelta(days=1)
                current = values[period.year, period.month]
                prior = values[previous.year, previous.month]
                older = values.get((earlier.year, earlier.month))
                actual = (current / prior - 1) * 100
                summary = "最終需要・季節調整済み前月比"
                release = "ppi"
            else:
                jobs = value("CES0000000001", period.year, period.month) - value("CES0000000001", previous.year, previous.month)
                rate = value("LNS14000000", period.year, period.month)
                summary = f"非農業部門雇用者数 前月比 {jobs * 1000:+,.0f}人・失業率 {rate:.1f}％"
                earlier = previous.replace(day=1) - timedelta(days=1)
                earlier_jobs = series["CES0000000001"].get((earlier.year, earlier.month))
                prior_jobs = value("CES0000000001", previous.year, previous.month)
                prior_rate = series["LNS14000000"].get((previous.year, previous.month))
                metrics = [
                    dict(label="非農業部門雇用者数 前月差",
                         current=f"{jobs * 1000:+,.0f}人",
                         previous=f"{(prior_jobs - earlier_jobs) * 1000:+,.0f}人"
                         if earlier_jobs is not None else None),
                    dict(label="失業率", current=f"{rate:.1f}%",
                         previous=f"{prior_rate:.1f}%" if prior_rate is not None else None),
                ]
                initial_jobs = payroll_at_release(day, period, previous)
                if initial_jobs is not None and initial_jobs != round(jobs * 1000):
                    metrics[0]["initialRelease"] = f"{initial_jobs:+,}人"
                    metrics[0]["revisionSource"] = "https://fred.stlouisfed.org/series/PAYEMS"
                release = "empsit"
        except (KeyError, ZeroDivisionError):
            continue
        event["result"] = dict(
            url=f"https://www.bls.gov/news.release/archives/{release}_{day:%m%d%Y}.htm",
            publishedAt=stamp.isoformat(),
            summary=f"{period.year}年{period.month}月分 · {summary}（BLS公表系列から計算、改定を含む）",
        )
        if release == "ppi":
            metrics = [dict(label="PPI 前月比", current=f"{actual:+.1f}%",
                previous=f"{(prior / older - 1) * 100:+.1f}%" if older else None)]
        if metrics:
            event["result"]["metrics"] = metrics


def attach_bea_results(events, now):
    try:
        root = ElementTree.fromstring(fetch("https://apps.bea.gov/rss/rss.xml").content)
    except (requests.RequestException, ElementTree.ParseError) as error:
        print(f"BEA feed unavailable: {error}")
        return []
    headlines = []
    for item in root.findall("./channel/item")[:25]:
        title, url, published = (item.findtext(field, "").strip() for field in ("title", "link", "pubDate"))
        target = urlsplit(url)
        if target.scheme != "https" or target.hostname != "www.bea.gov" or not published:
            continue
        stamp = parsedate_to_datetime(published).astimezone(JST)
        if stamp > now:
            continue
        headlines.append(dict(title=title, url=url, date=stamp.isoformat(), publisher="BEA"))
        if stamp < now - timedelta(days=105):
            continue
        description = BeautifulSoup(item.findtext("description", ""), "html.parser").get_text(" ", strip=True)
        if re.match(r"GDP[ ,(]", title):
            match = re.search(r"annual rate of ([\d.]+) percent", description)
            if not match:
                continue
            previous = re.search(r"real GDP (increased|decreased) ([\d.]+) percent", description)
            current = ("-" if "decreased at an annual rate" in description else "") + match[1] + "%"
            prior = (("-" if previous[1] == "decreased" else "") + previous[2] + "%") if previous else None
            label, release = "実質GDP 前期比年率", 53
        elif title.startswith("Personal Income and Outlays,"):
            try:
                page = BeautifulSoup(fetch(url).text, "html.parser")
            except requests.RequestException as error:
                print(f"BEA release unavailable: {error}")
                continue
            row = next((row for row in page.select("tr")
                        if row.find(["th", "td"]) and row.find(["th", "td"]).get_text(" ", strip=True) == "PCE price index"), None)
            values = [cell.get_text(strip=True) for cell in row.find_all(["td", "th"])[1:]] if row else []
            values = [value.replace("−", "-") + "%" for value in values if re.fullmatch(r"[-−]?[\d.]+", value)]
            if len(values) < 2:
                continue
            prior, current = values[-2:]
            label, release = "PCE価格指数 前月比", 54
        else:
            continue
        day = stamp.date().isoformat()
        event = next((row for row in events if row["date"] == day and row["title"] == RELEASES[release]), None)
        if event is None:
            event = dict(date=day, time=stamp.strftime("%H:%M"), title=RELEASES[release],
                         category="経済指標", region="米国", detail="BEA公式発表", url=url)
            events.append(event)
        event["result"] = dict(url=url, publishedAt=stamp.isoformat(), summary=title,
                               metrics=[dict(label=label, current=current, previous=prior)])
    return headlines


def official_rss_news(feed, host, publisher):
    try:
        root = ElementTree.fromstring(fetch(feed).content)
        items = []
        for entry in root.findall("./channel/item")[:8]:
            title, url, stamp = (entry.findtext(field, "").strip() for field in ("title", "link", "pubDate"))
            target = urlsplit(url)
            if title and stamp and target.scheme in ("http", "https") and target.hostname == host:
                items.append(dict(title=title, url=target._replace(scheme="https").geturl(), publisher=publisher,
                                  date=parsedate_to_datetime(stamp).astimezone(JST).isoformat()))
        return items
    except (requests.RequestException, ElementTree.ParseError, ValueError) as error:
        print(f"{publisher} news unavailable: {error}")
        return []


ENERGY_SERIES = (
    ("DCOILWTICO", "WTI原油", "ドル／バレル"),
    ("DCOILBRENTEU", "ブレント原油", "ドル／バレル"),
    ("DHHNGSP", "ヘンリーハブ天然ガス", "ドル／MMBtu"),
)
MARKET_SERIES = (
    ("DEXJPUS", "米ドル／円", "円／ドル"),
    ("DGS10", "米国10年国債利回り", "%"),
    ("DTWEXBGS", "FRB貿易加重ドル指数", "指数（2006年1月＝100）"),
)


def fred_history(now, previous, series):
    cached = {row["code"]: row for row in previous}
    results = []
    for code, name, unit in series:
        try:
            response = fetch("https://fred.stlouisfed.org/graph/fredgraph.csv",
                             params={"id": code, "cosd": (now.date() - timedelta(days=75)).isoformat()})
            history = [dict(date=row["observation_date"], price=float(row[code]))
                       for row in csv.DictReader(StringIO(response.text)) if row.get(code) not in (None, "", ".")]
            if len(history) < 2:
                raise ValueError("insufficient price observations")
            results.append(dict(code=code, name=name, unit=unit, history=history[-30:],
                                url=f"https://fred.stlouisfed.org/series/{code}"))
        except (requests.RequestException, KeyError, ValueError) as error:
            print(f"FRED {code}: {error}")
            if code in cached:
                results.append(cached[code])
    return results


def attach_earnings_results(events, now):
    first_day = now.date() - timedelta(days=220)
    sources = {}
    previous_metrics = {}
    try:
        for year in range(first_day.year, now.year + 1):
            origin = "https://ir.homedepot.com"
            for number in range(1, 4):
                archive = BeautifulSoup(fetch(f"{origin}/news-releases/{year}", params={"page": number},
                                              headers={"User-Agent": "Mozilla/5.0"}).text, "html.parser")
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
            for link in page.select("a[href]"):
                url = urljoin(event["url"], link["href"])
                if url.startswith("https://corporate.walmart.com/news/") and re.search(r"/walmart-releases-.*-earnings$", url):
                    sources["WMT", date.fromisoformat(event["date"])] = url
                    break
    except (requests.RequestException, ValueError) as error:
        print(f"WMT results archive: {error}")
    for (symbol, day), url in sorted(sources.items(), key=lambda entry: entry[0][1]):
        if not first_day <= day <= now.date():
            continue
        try:
            page = BeautifulSoup(fetch(url, headers={"User-Agent": "Mozilla/5.0"}).text, "html.parser")
        except requests.RequestException as error:
            print(f"{symbol} results for {day}: {error}")
            continue
        body = " ".join(page.stripped_strings)
        facts = []
        metrics = []
        if symbol == "HD":
            sales = re.search(r"reported sales of \$([\d.]+) billion", body, re.I)
            eps = re.search(r"or \$([\d.]+) per diluted share", body, re.I)
            if sales:
                facts.append(f"売上高 {float(sales[1]) * 10:g}億ドル")
                metrics.append(("売上高", float(sales[1]) * 10, "億ドル", "億ドル"))
            if eps:
                facts.append(f"希薄化後EPS {eps[1]}ドル")
                metrics.append(("希薄化後EPS", float(eps[1]), "ドル", "ドル"))
        else:
            growth = re.search(r"Total revenues\s+Q\d FY\d+\s+([+−-]?[\d.]+)%", body)
            if growth:
                amount = float(growth[1].replace("−", "-"))
                facts.append(f"総収益 前年同期比 {amount:+g}％")
                metrics.append(("総収益 前年同期比", amount, "%", "ポイント"))
        comparison = []
        for label, current, unit, delta_unit in metrics:
            prior = previous_metrics.get((symbol, label))
            comparison.append(dict(label=label, current=f"{current:g}{unit}",
                                   previous=f"{prior:g}{unit}" if prior is not None else None,
                                   change=f"{current - prior:+.4g}{delta_unit}" if prior is not None else None))
            previous_metrics[symbol, label] = current
        key = day.isoformat()
        event = next((row for row in events if row["date"] == key
                      and row["category"] == "決算" and row["title"].startswith(symbol + " ")), None)
        if event is None:
            event = dict(date=key, time="", title=f"{symbol} 決算発表",
                         category="決算", region="米国", detail="企業公式IR", url=url)
            events.append(event)
        event["result"] = dict(url=url, publishedAt=key,
                               summary="・".join(facts) if facts else "企業が決算結果を公表しました。",
                               metrics=comparison, consensusAvailable=False)


def preserve_result_history(events, observed_at):
    if not OUT.exists():
        return
    try:
        old = json.loads(OUT.read_text(encoding="utf-8").removeprefix("window.MARKET_CALENDAR = ").strip().removesuffix(";"))
    except (OSError, ValueError):
        return
    def key(event):
        return event["date"], event["title"]
    old_results = {key(event): event for event in old["events"] if event.get("result")}
    present = set()
    for event in events:
        event_key = key(event)
        present.add(event_key)
        old_event = old_results.get(event_key, {})
        previous = old_event.get("result")
        if not previous:
            continue
        if not event.get("result"):
            event["result"] = previous
            continue
        result = event["result"]
        for metric in result.get("metrics", []):
            earlier = next((row for row in previous.get("metrics", []) if row["label"] == metric["label"]), None)
            if not earlier:
                continue
            for field in ("initialRelease", "revisionSource"):
                if field in earlier:
                    metric.setdefault(field, earlier[field])
            if metric["current"] == earlier["current"] and earlier.get("revisionSource"):
                metric["revisionSource"] = earlier["revisionSource"]
            metric["firstObserved"] = earlier.get("firstObserved", earlier["current"])
            metric["revisions"] = earlier.get("revisions", [])
            if metric["current"] != earlier["current"]:
                metric["revisions"] = [*metric["revisions"], dict(at=observed_at, value=metric["current"])]
    cutoff = (datetime.fromisoformat(observed_at).date() - timedelta(days=220)).isoformat()
    events.extend(event for event_key, event in old_results.items()
                  if event_key not in present and cutoff <= event["date"])


def compare_gdp_estimates(events):
    first = {}
    for event in sorted(events, key=lambda row: row["date"]):
        if event["title"] != RELEASES[53] or not event.get("result"):
            continue
        result = event["result"]
        period = re.search(r"([1-4](?:st|nd|rd|th) Quarter \d{4})", result["summary"], re.I)
        metrics = result.get("metrics", [])
        if not period or not metrics:
            continue
        metric = metrics[0]
        key = period[1].lower()
        if "advance estimate" in result["summary"].lower():
            first[key] = metric["current"]
        elif key in first:
            metric["initialRelease"] = first[key]


def filing_comparison(quarters, index):
    quarter = quarters[index]
    prior = quarters[index + 1] if index + 1 < len(quarters) else {}
    if prior and not 75 <= (date.fromisoformat(quarter["period"]) - date.fromisoformat(prior["period"])).days <= 105:
        prior = {}
    metrics = []
    for key, label, scale, suffix in (("revenue", "売上高", 1e8, "億ドル"),
                                       ("netIncome", "純利益", 1e8, "億ドル"),
                                       ("eps", "希薄化後EPS", 1, "ドル")):
        current = quarter.get(key)
        previous = prior.get(key)
        if current is None:
            continue
        change = (current - previous) / scale if previous is not None else None
        metrics.append(dict(label=label, current=f"{current / scale:.2f}{suffix}",
                            previous=f"{previous / scale:.2f}{suffix}" if previous is not None else None,
                            change=f"{change:+.2f}{suffix}" if change is not None else None))
    return metrics


def add_walmart_filing_metrics(events, companies):
    quarters = next((company["quarters"] for company in companies if company["symbol"] == "WMT"), [])
    for event in events:
        result = event.get("result")
        if event["title"] != "WMT 決算発表" or not result:
            continue
        release = re.search(r"/walmart-releases-q([1-4])-fy([0-9]{2})-earnings", result["url"])
        if not release:
            continue
        fiscal_quarter, fiscal_year = map(int, release.groups())
        period_month = (4, 7, 10, 1)[fiscal_quarter - 1]
        period_year = 2000 + fiscal_year - (fiscal_quarter != 4)
        for index, quarter in enumerate(quarters):
            period = date.fromisoformat(quarter["period"])
            if (period.year, period.month) != (period_year, period_month):
                continue
            metrics = filing_comparison(quarters, index)
            labels = {metric["label"] for metric in metrics}
            result["metrics"] = [metric for metric in result.get("metrics", []) if metric["label"] not in labels] + metrics
            result["filingUrl"] = quarter["url"]
            break


def add_issuer_release_events(events, companies, today):
    cutoff = (today - timedelta(days=220)).isoformat()
    for company in companies:
        symbol = company["symbol"]
        for index, quarter in enumerate(company["quarters"]):
            day = quarter.get("releaseDate")
            if not day or not cutoff <= day <= today.isoformat():
                continue
            title = f"{symbol} 決算発表"
            if any(row["date"] == day and row["title"] == title for row in events):
                continue
            metrics = filing_comparison(company["quarters"], index)
            url = quarter["releaseUrl"]
            events.append(dict(date=day, time="", title=title, category="決算", region="米国",
                               detail="企業公式IR・現地日付", url=url,
                               result=dict(url=url, publishedAt=day, summary=f"{quarter['period']}終了四半期",
                                           metrics=metrics)))


def main():
    now = datetime.now(JST)
    start = now.date().replace(day=1)
    next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
    end = next_month.replace(day=calendar.monthrange(next_month.year, next_month.month)[1])
    prior_month = (start - timedelta(days=1)).replace(day=1)
    events = economy(prior_month - timedelta(days=1), end) + holidays(start, end)
    issuer_status = {}
    for symbol, source in {"HD": issuer_earnings, "WMT": walmart_earnings, "NVDA": nvidia_earnings}.items():
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
    bea_news = attach_bea_results(events, now)
    result_start = (start - timedelta(days=1)).replace(day=1)
    attach_fomc_results(events, news, result_start)
    attach_earnings_results(events, now)
    preserve_result_history(events, now.isoformat(timespec="seconds"))
    compare_gdp_estimates(events)
    try:
        previous = json.loads(OUT.read_text(encoding="utf-8").removeprefix("window.MARKET_CALENDAR = ").strip().removesuffix(";"))
    except (OSError, ValueError):
        previous = {}
    fundamentals = company_fundamentals(fetch, now.date(), previous.get("fundamentals", []))
    add_issuer_release_events(events, fundamentals, now.date())
    add_walmart_filing_metrics(events, fundamentals)
    issuer_news = []
    for event in events:
        result = event.get("result")
        if event["category"] != "決算" or not result:
            continue
        publisher = {"ir.homedepot.com": "Home Depot公式IR",
                     "corporate.walmart.com": "Walmart公式IR", "www.apple.com": "Apple公式Newsroom",
                     "www.microsoft.com": "Microsoft公式IR", "nvidianews.nvidia.com": "NVIDIA公式Newsroom"}.get(urlsplit(result["url"]).hostname)
        if publisher:
            issuer_news.append(dict(title=f'{event["title"]} · {result["summary"]}',
                                    url=result["url"], date=result["publishedAt"], publisher=publisher))
    filings = [dict(title=f'{company["symbol"]} 四半期報告書（Form 10-Q）',
                    url=company["quarters"][0]["url"], date=company["quarters"][0]["filed"], publisher="SEC EDGAR")
               for company in fundamentals if company["quarters"][0].get("filed")]
    payload = dict(updatedAt=now.isoformat(timespec="seconds"), coverage=[start.isoformat(), end.isoformat()],
                   events=sorted((e for e in events if (start.isoformat() <= e["date"] <= end.isoformat()) or e.get("result")),
                                 key=lambda e: (e["date"], e["time"], e["title"])),
                   analystTrends=trends, news=sorted(news + bea_news[:12] + official_rss_news("https://www.ecb.europa.eu/rss/press.html", "www.ecb.europa.eu", "ECB")
                                                    + official_rss_news("https://www.boj.or.jp/rss/whatsnew.xml", "www.boj.or.jp", "日本銀行")
                                                    + official_rss_news("https://www.eia.gov/rss/todayinenergy.xml", "www.eia.gov", "EIA")
                                                    + official_rss_news("https://www.census.gov/economic-indicators/indicator.xml", "www.census.gov", "U.S. Census Bureau")
                                                    + official_rss_news("https://www.jpx.co.jp/rss/markets_news.xml", "www.jpx.co.jp", "JPX") + filings + issuer_news,
                                                    key=lambda item: item["date"], reverse=True),
                   fundamentals=fundamentals,
                   energyPrices=fred_history(now, previous.get("energyPrices", []), ENERGY_SERIES),
                   marketRates=fred_history(now, previous.get("marketRates", []), MARKET_SERIES),
                   licensedData=enabled, issuerStatus=issuer_status)
    temp = OUT.with_suffix(".tmp")
    temp.write_text("window.MARKET_CALENDAR = " + json.dumps(payload, ensure_ascii=False, indent=2) + ";\n", encoding="utf-8")
    temp.replace(OUT)
    print(f"Updated {len(payload['events'])} events")


if __name__ == "__main__":
    main()

import React from "react";
import { createRoot } from "react-dom/client";
import { MarketCalendarPanel } from "./MarketCalendarPanel";
import "./style.css";

const data = window.MARKET_CALENDAR;
const today = new Intl.DateTimeFormat("sv-SE", {timeZone: "Asia/Tokyo"}).format(new Date());
const sourceHosts = new Set([
  "fred.stlouisfed.org", "www.nyse.com", "ir.homedepot.com", "corporate.walmart.com",
]);
const events = data.events.filter(event => {
  try {
    const source = new URL(event.url);
    return source.protocol === "https:" && sourceHosts.has(source.hostname);
  } catch {
    return false;
  }
}).map(event => ({
  date: event.date,
  name: event.title,
  symbol: event.title.split(" ")[0],
  type: event.category === "決算" ? "earnings" : "macro",
  note: [event.time, event.detail].filter(Boolean).join(" · "),
  url: event.url,
}));
createRoot(document.getElementById("market-calendar")).render(
  <>
    <p className="mb-3 text-xs text-slate-500">更新 {data.updatedAt.slice(0, 10)} · JST</p>
    <MarketCalendarPanel events={events} today={today} />
    <section className="mt-6" aria-labelledby="news-heading">
      <h2 id="news-heading">市場ニュース（FRB）</h2>
      <ul className="space-y-2 text-sm">
        {data.news.filter(item => item.url.startsWith("https://www.federalreserve.gov/")).map(item => (
          <li key={item.url}>{item.date} · <a className="text-indigo-700 underline" href={item.url}>{item.title}</a></li>
        ))}
      </ul>
    </section>
  </>
);

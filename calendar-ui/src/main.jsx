import React, { useState } from "react";
import { EnergyPanel } from "./EnergyPanel";
import { FundamentalsPanel } from "./FundamentalsPanel";
import { NewsPanel } from "./NewsPanel";
import { createRoot } from "react-dom/client";
import { MarketCalendarPanel } from "./MarketCalendarPanel";
import "./style.css";

const data = window.MARKET_CALENDAR;
const today = new Intl.DateTimeFormat("sv-SE", {timeZone: "Asia/Tokyo"}).format(new Date());
const sourceHosts = new Set([
  "fred.stlouisfed.org", "www.nyse.com", "www.federalreserve.gov", "www.bea.gov", "ir.homedepot.com", "corporate.walmart.com",
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
  result: event.result,
}));
function PublicMarketTabs() {
  const [tab, setTab] = useState("calendar");
  const todaysEvents = events.filter(event => event.date === today);
  const tabs = [
    ["schedule", "🗓 本日予定"],
    ["calendar", "📅 カレンダー"],
    ["results", "発表済み"],
    ["news", "📰 ニュース"],
    ["fundamentals", "決算書・財務指標"],
    ["energy", "商品価格"],
  ];
  return (
    <>
      <nav aria-label="市場環境" className="flex items-center gap-1.5 flex-wrap mb-3">
        <span className="text-[9px] font-black text-indigo-500 shrink-0">📰 市場環境</span>
        {tabs.map(([key, label]) => (
          <button key={key} onClick={() => setTab(key)} aria-pressed={tab === key}
            className={`text-[11px] px-2.5 py-1 rounded-full border font-bold transition ${tab === key ? "bg-indigo-600 text-white border-indigo-600" : "bg-white text-slate-600 border-slate-300 hover:border-slate-400"}`}>
            {label}
          </button>
        ))}
      </nav>
      <p className="mb-3 text-xs text-slate-500">更新 {data.updatedAt.slice(0, 10)} · JST</p>
      {tab === "calendar" && <MarketCalendarPanel events={events} today={today} />}
      {tab === "schedule" && (todaysEvents.length
        ? <MarketCalendarPanel events={todaysEvents} today={today} />
        : <p className="text-center py-10 text-slate-500 text-sm">{today} の収録イベントはありません。</p>)}
      {tab === "results" && <MarketCalendarPanel events={events.filter(event => event.result)} today={today} newestFirst />}
      {tab === "news" && <NewsPanel news={data.news} />}
      {tab === "fundamentals" && <>
        <FundamentalsPanel companies={data.fundamentals ?? []} />
        <h3 className="mb-2 mt-4 font-semibold">企業の公式決算発表</h3>
        <MarketCalendarPanel events={events.filter(event => event.type === "earnings" && event.result)} today={today} newestFirst />
      </>}
      {tab === "energy" && <EnergyPanel series={data.energyPrices ?? []} />}
    </>
  );
}

createRoot(document.getElementById("market-calendar")).render(<PublicMarketTabs />);

import React from "react";

export function MarketCalendarPanel({ events, today, newestFirst = false }) {
  const IMPACT_STYLE = {

    VERY_HIGH: { border: "border-rose-300",   bg: "bg-rose-50",   badge: "bg-rose-100 text-rose-800 border-rose-300",   dot: "bg-rose-500" },

    HIGH:      { border: "border-amber-300",  bg: "bg-amber-50",  badge: "bg-amber-100 text-amber-800 border-amber-300", dot: "bg-amber-500" },

    MEDIUM:    { border: "border-blue-200",   bg: "bg-blue-50",   badge: "bg-blue-50 text-blue-700 border-blue-200",    dot: "bg-blue-400" },

  };



  const groupedByDate = events.reduce((groups, event) => {
    (groups[event.date] ??= []).push(event);
    return groups;
  }, {});
  return (
    <div className="space-y-3">
      {Object.entries(groupedByDate).sort(([a], [b]) => newestFirst ? b.localeCompare(a) : a.localeCompare(b)).map(([dateStr, events]) => {
        const d = new Date(dateStr + "T00:00:00");
        const isToday = dateStr === today;
        const dayLabel = ["日","月","火","水","木","金","土"][d.getDay()];
        const isSat = d.getDay() === 6, isSun = d.getDay() === 0;
        const daysUntil = Math.round((Date.parse(dateStr) - Date.parse(today)) / 86400000);
        const hasEarnings = events.some(e => e.type === "earnings");
        const hasVeryHigh = events.some(e => e.impact === "VERY_HIGH");
        return (
          <div key={dateStr} className={`rounded-xl border-2 overflow-hidden ${
            isToday ? "border-indigo-400 shadow-md" :
            hasVeryHigh ? "border-rose-300" :
            hasEarnings ? "border-amber-300" : "border-slate-200"
          }`}>
            {/* 日付バー */}
            <div className={`flex items-center gap-3 px-3 py-2 ${
              isToday ? "bg-indigo-600 text-white" :
              hasVeryHigh ? "bg-rose-50" :
              hasEarnings ? "bg-amber-50" : "bg-slate-50"
            }`}>
              <div className={`text-center shrink-0 w-14 ${isToday ? "text-white" : isSun ? "text-red-500" : isSat ? "text-blue-500" : "text-slate-700"}`}>
                <div className="text-base font-black leading-none">{dateStr.slice(8)}</div>
                <div className="text-[9px] font-bold">{dateStr.slice(5,7)}月 ({dayLabel})</div>
                {daysUntil === 0 && <div className="text-[8px] font-bold text-yellow-300 mt-0.5">本日</div>}
                {daysUntil > 0 && <div className={`text-[8px] ${isToday ? "text-indigo-200" : "text-slate-400"}`}>{daysUntil}日後</div>}
              </div>
              <div className="flex flex-wrap gap-1 flex-1">
                {events.map((ev, i) => {
                  const st = IMPACT_STYLE[ev.impact] || IMPACT_STYLE.MEDIUM;
                  return (
                    <span key={i} className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${st.badge}`}>
                      <span className={`inline-block w-1.5 h-1.5 rounded-full ${st.dot} mr-1`} />
                      {ev.type === "earnings" ? `📊 ${ev.symbol} 決算` : ev.name}
                    </span>
                  );
                })}
              </div>
            </div>
            <div className="divide-y divide-slate-100 bg-white">
              {events.map((ev, i) => (
                <div key={i} className="px-3 py-2.5">
                  <div className="font-bold text-slate-800 text-sm mb-1">{ev.name}</div>
                  {ev.note && <p className="text-[11px] text-slate-600 mb-1.5">{ev.note}</p>}
                  {ev.url && <a className="text-xs text-indigo-700 underline" href={ev.url}>出典</a>}
                  {ev.result && (
                    <div className="mt-2 rounded-md border border-indigo-200 bg-indigo-50 p-2 text-xs">
                      <strong>発表済み</strong>
                      <p>{ev.result.summary}</p>
                      {ev.result.metrics?.length > 0 && (
                        <table className="my-2 w-full text-left">
                          <thead><tr><th scope="col">指標</th><th scope="col">前回</th><th scope="col">今回</th><th scope="col">差</th></tr></thead>
                          <tbody>{ev.result.metrics.map(metric => (
                            <React.Fragment key={metric.label}>
                              <tr><th scope="row">{metric.label}</th><td>{metric.previous ?? "—"}</td><td>{metric.current}</td><td>{metric.change ?? "—"}</td></tr>
                              {metric.initialRelease && (
                                <tr><td colSpan={4}>初回公表値 {metric.initialRelease} · 改定値 {metric.current}{metric.revisionSource && <> · <a href={metric.revisionSource} target="_blank" rel="noopener noreferrer">改定の原文</a></>}</td></tr>
                              )}
                              {metric.revisions?.length > 0 && (
                                <tr><td colSpan={4}>初回取得 {metric.firstObserved} · 改定 {metric.revisions.map(revision => revision.value).join(" → ")}</td></tr>
                              )}
                            </React.Fragment>
                          ))}</tbody>
                        </table>
                      )}
                      {ev.result.consensusAvailable === false && <p>市場予想：公開可能なデータなし</p>}
                      <time dateTime={ev.result.publishedAt}>{ev.result.publishedAt.slice(0, 16).replace("T", " ")}{ev.result.publishedAt.includes("T") ? " JST" : "（現地日付）"}</time>
                      {" · "}<a className="text-indigo-700 underline" href={ev.result.url}>公式発表の原文</a>
                      {ev.result.filingUrl && <>{" · "}<a className="text-indigo-700 underline" href={ev.result.filingUrl}>四半期報告書</a></>}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

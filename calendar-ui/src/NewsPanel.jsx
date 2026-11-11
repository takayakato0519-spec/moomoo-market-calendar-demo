import React, { useState } from "react";

export function NewsPanel({ news }) {
  const [publisher, setPublisher] = useState("");
  const entries = news.filter(item => ["https://www.federalreserve.gov/", "https://www.bea.gov/", "https://www.ecb.europa.eu/", "https://www.boj.or.jp/", "https://www.eia.gov/todayinenergy/", "https://www.sec.gov/Archives/edgar/", "https://ir.homedepot.com/news-releases/", "https://corporate.walmart.com/news/"].some(prefix => item.url.startsWith(prefix))).map(item => ({
    _sym: "市場全体",
    publisher: item.publisher || "FRB",
    title: item.title,
    link: item.url,
    published_at: item.date,
  }));
  const publishers = [...new Set(entries.map(item => item.publisher))].sort();
  const items = publisher ? entries.filter(item => item.publisher === publisher) : entries;
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 mb-3 flex-wrap">
        <span className="text-xs text-slate-500 font-bold">公式発表</span>
        <label className="text-xs">発表元 <select value={publisher} onChange={event => setPublisher(event.target.value)}>
          <option value="">すべて</option>
          {publishers.map(name => <option key={name}>{name}</option>)}
        </select></label>
        <span className="text-[10px] text-slate-400 ml-auto">{items.length}件</span>
      </div>
              {items.map((item) => {
                const score = item.sentiment_score ?? 0;
                const isJP = item._sym?.endsWith(".T");
                return (
                  <div key={item.link} className={`rounded-lg border p-2.5 flex gap-2.5 ${
                    score >= 0.15 ? "border-green-200 bg-green-50" :
                    score <= -0.15 ? "border-rose-200 bg-rose-50" :
                    "border-slate-200 bg-white"
                  }`}>
                    {/* 銘柄バッジ */}
                    <div className="shrink-0 pt-0.5">
                      <span className={`text-[10px] font-black px-2 py-1 rounded-md ${isJP ? "bg-red-100 text-red-800" : "bg-blue-100 text-blue-800"}`}>
                        {item._sym}
                      </span>
                    </div>
                    {/* ニュース本文 */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-1">
                        <p className="text-[12px] font-semibold text-slate-800 leading-snug line-clamp-2">
                          {item.link ? (
                            <a href={item.link} target="_blank" rel="noopener noreferrer" className="hover:text-indigo-700 hover:underline">
                              {item.title}
                            </a>
                          ) : item.title}
                        </p>
                      </div>
                      {item.summary && (
                        <p className="text-[10px] text-slate-500 mt-0.5 line-clamp-2">{item.summary}</p>
                      )}
                      <div className="flex items-center gap-2 mt-1 text-[9px] text-slate-400">
                        <span>{item.publisher || "不明"}</span>
                        {item.published_at && <span>· {item.published_at.slice(0,10)}</span>}
                        {isJP && <span className="text-red-400">🇯🇵 JP株</span>}
                      </div>
                    </div>
                  </div>
                );
              })}
    </div>
  );
}

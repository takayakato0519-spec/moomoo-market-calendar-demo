import React from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export function EnergyPanel({ series, title = "エネルギー現物価格", source = "米EIA公表系列（FRED）" }) {
  if (!series.length) return <p>データを取得できていません。</p>;
  return (
    <section>
      <h3 className="mb-2 font-semibold">{title}</h3>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {series.map(item => {
          const latest = item.history.at(-1);
          const prior = item.history.at(-2);
          const delta = latest.price - prior.price;
          return (
            <article key={item.code} className="rounded-xl border border-slate-200 bg-slate-50 p-3">
              <h4 className="font-black text-slate-800">{item.name}</h4>
              <p className="mb-2 text-sm">
                <strong>{latest.price.toFixed(2)}</strong> {item.unit}
                <span className={delta >= 0 ? "ml-2 text-green-700" : "ml-2 text-rose-700"}>
                  {delta >= 0 ? "+" : ""}{delta.toFixed(2)}{item.unit === "%" ? "ポイント" : ""}
                </span>
              </p>
              <div className="h-28">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={item.history}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="date" tickFormatter={date => date.slice(5)} tick={{ fontSize: 8 }} minTickGap={24} />
                    <YAxis domain={["dataMin", "dataMax"]} width={34} tick={{ fontSize: 8 }} />
                    <Tooltip formatter={price => [price, item.unit]} />
                    <Line type="monotone" dataKey="price" stroke="#1e293b" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <p className="text-xs text-slate-600">{latest.date} · 前回観測値との差</p>
              <a className="text-xs text-indigo-700 underline" href={item.url}>{source}</a>
            </article>
          );
        })}
      </div>
    </section>
  );
}

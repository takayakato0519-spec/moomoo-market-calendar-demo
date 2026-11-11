import React, { useState } from "react";

import { MetricCard } from "./MetricCard";

const number = new Intl.NumberFormat("ja-JP", { maximumFractionDigits: 2 });
const billions = value => value == null ? "—" : number.format(value / 1e8);

export function FundamentalsPanel({ companies }) {
  const [symbol, setSymbol] = useState(companies[0]?.symbol);
  const company = companies.find(row => row.symbol === symbol);
  if (!company) return <p>四半期報告書のデータを取得できていません。</p>;
  const latest = company.quarters[0];
  return (
    <section className="rounded-xl border border-teal-200 bg-teal-50 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-black text-teal-800">決算書・財務指標</h3>
        <label className="text-sm">銘柄 <select value={symbol} onChange={event => setSymbol(event.target.value)}>
          {companies.map(row => <option key={row.symbol}>{row.symbol}</option>)}
        </select></label>
      </div>
      <p className="mb-2 text-sm text-slate-700">{company.name} · {company.publisher ?? "SEC EDGAR"}の四半期報告書</p>
      <div className="mb-3 grid gap-2 sm:grid-cols-3">
        <MetricCard label="売上高（億ドル）" value={billions(latest.revenue)} sub={latest.period} tone="teal" />
        <MetricCard label="純利益（億ドル）" value={billions(latest.netIncome)} sub={latest.period} tone="emerald" />
        <MetricCard label="希薄化後EPS（ドル）" value={latest.eps == null ? "—" : number.format(latest.eps)} sub={latest.period} tone="amber" />
      </div>
      <div className="overflow-x-auto">
        <table className="w-full whitespace-nowrap text-left text-sm">
          <thead><tr><th>四半期末</th><th>売上高（億ドル）</th><th>純利益（億ドル）</th><th>希薄化後EPS（ドル）</th><th>提出書類</th></tr></thead>
          <tbody>{company.quarters.map(row => (
            <tr key={row.period} className="border-t border-teal-200">
              <th scope="row" className="py-2 pr-3">{row.period}</th>
              <td>{billions(row.revenue)}</td><td>{billions(row.netIncome)}</td>
              <td>{row.eps == null ? "—" : number.format(row.eps)}</td>
              <td><a className="text-indigo-700 underline" href={row.url}>10-Q 原文</a></td>
            </tr>
          ))}</tbody>
        </table>
      </div>
      <p className="mt-2 text-xs text-slate-600">10-Qに記載された約3カ月の実績。通期報告書で公表される第4四半期は対象外です。</p>
      <a className="text-xs text-indigo-700 underline" href={company.source}>財務資料の出典</a>
    </section>
  );
}

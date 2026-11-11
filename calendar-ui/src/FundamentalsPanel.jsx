import React, { useState } from "react";

import { MetricCard } from "./MetricCard";

const number = new Intl.NumberFormat("ja-JP", { maximumFractionDigits: 2 });
const billions = value => value == null ? "—" : number.format(value / 1e8);

const signedPercent = new Intl.NumberFormat("ja-JP", {
  style: "percent", maximumFractionDigits: 1, signDisplay: "exceptZero",
});

const percent = new Intl.NumberFormat("ja-JP", { style: "percent", maximumFractionDigits: 1 });

function netMargin(row) {
  return row.revenue > 0 && Number.isFinite(row.netIncome)
    ? percent.format(row.netIncome / row.revenue)
    : "—";
}

function quarterChange(current, previous, key) {
  const days = (Date.parse(current.period) - Date.parse(previous?.period)) / 86400000;
  if (!(days >= 75 && days <= 105) || !Number.isFinite(current[key]) || !(previous[key] > 0)) {
    return "—";
  }
  return signedPercent.format((current[key] - previous[key]) / previous[key]);
}

export function FundamentalsPanel({ companies }) {
  const [symbol, setSymbol] = useState(companies[0]?.symbol);
  const company = companies.find(row => row.symbol === symbol);
  if (!company) return <p>四半期報告書のデータを取得できていません。</p>;
  const latest = company.quarters[0];
  const outlook = latest.nextRevenueOutlook;
  const prior = company.quarters[1];
  const priorOutlook = prior?.nextRevenueOutlook;
  const priorDays = (Date.parse(latest.period) - Date.parse(prior?.period)) / 86400000;
  return (
    <section className="rounded-xl border border-teal-200 bg-teal-50 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-black text-teal-800">決算書・財務指標</h3>
        <label className="text-sm">銘柄 <select value={symbol} onChange={event => setSymbol(event.target.value)}>
          {companies.map(row => <option key={row.symbol}>{row.symbol}</option>)}
        </select></label>
      </div>
      <p className="mb-2 text-sm text-slate-700">{company.name} · {company.publisher ?? "SEC EDGAR"}の決算資料</p>
      <div className="mb-3 grid gap-2 sm:grid-cols-3">
        <MetricCard label="売上高（億ドル）" value={billions(latest.revenue)} sub={latest.period} tone="teal" />
        <MetricCard label="純利益（億ドル）" value={billions(latest.netIncome)} sub={latest.period} tone="emerald" />
        <MetricCard label="希薄化後EPS（ドル）" value={latest.eps == null ? "—" : number.format(latest.eps)} sub={latest.period} tone="amber" />
      </div>
      {outlook && (
        <p className="mb-2 text-sm">
          会社公表の次四半期売上高見通し {billions(outlook.midpoint)}億ドル（±{percent.format(outlook.tolerance)}）
          {" · "}<a className="text-indigo-700 underline" href={latest.url}>見通しの原文</a>
        </p>
      )}
      {priorOutlook && priorDays >= 75 && priorDays <= 105 && Number.isFinite(latest.revenue) && (
        <p className="mb-3 text-sm">
          今回の売上高 {billions(latest.revenue)}億ドル · 前回発表時の会社見通し {billions(priorOutlook.midpoint)}億ドル
          {" · 中心値との差 "}{signedPercent.format(latest.revenue / priorOutlook.midpoint - 1)}
          {" · "}<a className="text-indigo-700 underline" href={prior.url}>前回の原文</a>
        </p>
      )}
      <div className="overflow-x-auto">
        <table className="w-full whitespace-nowrap text-left text-sm">
          <thead><tr><th>四半期末</th><th>売上高（億ドル）</th><th>純利益（億ドル）</th><th>希薄化後EPS（ドル）</th><th>純利益率</th><th>提出書類</th></tr></thead>
          <tbody>{company.quarters.map((row, index) => (
            <tr key={row.period} className="border-t border-teal-200">
              <th scope="row" className="py-2 pr-3">{row.period}</th>
              {[
                ["revenue", billions(row.revenue)],
                ["netIncome", billions(row.netIncome)],
                ["eps", row.eps == null ? "—" : number.format(row.eps)],
              ].map(([key, value]) => (
                <td key={key} className="pr-3">
                  {value}
                  <div className="text-xs text-slate-600">前期比 {quarterChange(row, company.quarters[index + 1], key)}</div>
                </td>
              ))}
              <td className="pr-3">{netMargin(row)}</td>
              <td><a className="text-indigo-700 underline" href={row.url}>公式原文</a></td>
            </tr>
          ))}</tbody>
        </table>
      </div>
      <p className="mt-2 text-xs text-slate-600">約3カ月の実績を表示。純利益率は純利益を売上高で割って計算します。連続する前四半期の値があり、その値が正の場合に前期比を表示します。</p>
      <a className="text-xs text-indigo-700 underline" href={company.source}>財務資料の出典</a>
    </section>
  );
}

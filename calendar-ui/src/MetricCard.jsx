import React from "react";

export function MetricCard({ label, value, sub, tone = "slate", warn = false, extra }) {
  const toneMap = {
    slate:   "border-slate-700/60 text-slate-100",
    teal:    "border-teal-600/60 text-teal-200",
    rose:    "border-rose-600/60 text-rose-200",
    amber:   "border-amber-600/60 text-amber-200",
    emerald: "border-emerald-600/60 text-emerald-200",
  };
  const border = warn ? "border-orange-500/70" : (toneMap[tone] || toneMap.slate).split(" ")[0];
  const valueColor = (toneMap[tone] || toneMap.slate).split(" ")[1];

  return (
    <div className={`rounded-xl border bg-slate-900 p-4 flex flex-col gap-1.5 ${border}`}>
      <div className="text-[11px] tracking-wide uppercase text-slate-400">{label}</div>
      <div className={`text-2xl font-bold font-mono leading-tight ${valueColor}`}>{value}</div>
      {sub && <div className="text-xs text-slate-500">{sub}</div>}
      {extra}
    </div>
  );
}

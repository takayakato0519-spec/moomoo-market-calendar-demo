"use strict";
function analyzeCross(csv, symbol) {
  const [header, ...lines] = csv.trim().split(/\r?\n/);
  const columns = header.replace(/^\uFEFF/, "").toLowerCase().split(",").map(s => s.trim());
  const d = columns.indexOf("date"), c = columns.indexOf("close"), s = columns.indexOf("symbol");
  if (d < 0 || c < 0) throw Error("CSVには date と close の列が必要です。");
  const prices = new Map();
  for (const line of lines) {
    if (!line.trim()) continue;
    const row = line.split(",").map(v => v.trim().replace(/^"|"$/g, ""));
    if (s >= 0 && row[s]?.toUpperCase() !== symbol) continue;
    const day = row[d], close = Number(row[c]);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(day) || !Number.isFinite(close) || close <= 0 || prices.has(day))
      throw Error("日付（YYYY-MM-DD）、終値、日付の重複を確認してください。");
    prices.set(day, close);
  }
  const rows = [...prices].sort(([a], [b]) => a.localeCompare(b));
  if (rows.length < 201) throw Error(`交差の判定には201営業日分が必要です（現在 ${rows.length} 件）。`);
  let short, long, prior, last;
  for (let i = 199; i < rows.length; i++) {
    short = rows.slice(i - 49, i + 1).reduce((sum, r) => sum + r[1], 0) / 50;
    long = rows.slice(i - 199, i + 1).reduce((sum, r) => sum + r[1], 0) / 200;
    const diff = short - long;
    if (prior <= 0 && diff > 0) last = [rows[i][0], "ゴールデンクロス"];
    if (prior >= 0 && diff < 0) last = [rows[i][0], "デッドクロス"];
    prior = diff;
  }
  return { short, long, date: rows.at(-1)[0], last };
}

if (typeof module !== "undefined") module.exports = analyzeCross;
if (typeof document !== "undefined") document.getElementById("cross-form").addEventListener("submit", async event => {
  event.preventDefault();
  const result = document.getElementById("cross-result");
  try {
    const symbol = document.getElementById("cross-symbol").value.trim().toUpperCase();
    if (!/^[A-Z0-9.^=-]{1,20}$/.test(symbol)) throw Error("銘柄コードを確認してください。");
    const csv = await document.getElementById("cross-file").files[0].text();
    const { short, long, date, last } = analyzeCross(csv, symbol);
    result.textContent = `${symbol}（${date}） 50日線 ${short.toFixed(2)} / 200日線 ${long.toFixed(2)} · ${last ? last.join(" ") : "収録期間中の交差なし"}`;
  } catch (error) {
    result.textContent = error.message;
  }
});

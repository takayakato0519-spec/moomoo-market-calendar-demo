"use strict";

document.getElementById("depth-file").addEventListener("change", async event => {
  const file = event.target.files[0];
  const status = document.getElementById("depth-status");
  const table = document.getElementById("depth-table");
  const body = table.tBodies[0];
  body.replaceChildren();
  table.hidden = true;
  status.textContent = "";
  if (!file) return;
  try {
    if (file.size > 1000000) throw new Error("1 MB以下のCSVを選んでください。");
    const content = await file.text();
    if (event.target.files[0] !== file) return;
    const [header, ...lines] = content.trim().split(/\r?\n/);
    if (header.trim().toLowerCase() !== "side,price,size") throw new Error("列名は side,price,size にしてください。");
    const levels = { bid: new Map(), ask: new Map() };
    for (const line of lines) {
      if (!line.trim()) continue;
      const fields = line.split(",").map(value => value.trim());
      const [side, rawPrice, rawSize] = fields;
      const price = Number(rawPrice);
      const size = Number(rawSize);
      if (fields.length !== 3 || !Object.hasOwn(levels, side) || !Number.isFinite(price) ||
          !Number.isFinite(size) || price <= 0 || size <= 0) throw new Error("bid/ask、価格、数量を確認してください。");
      const total = (levels[side].get(price) ?? 0) + size;
      if (!Number.isFinite(total)) throw new Error("数量の合計が大きすぎます。");
      levels[side].set(price, total);
    }
    for (const side of ["bid", "ask"]) {
      const rows = [...levels[side]].sort((a, b) => side === "bid" ? b[0] - a[0] : a[0] - b[0]);
      for (const [price, size] of rows.slice(0, 20)) {
        const row = body.insertRow();
        for (const value of [side === "bid" ? "買い" : "売り", price, Number(size.toPrecision(12))]) {
          row.insertCell().textContent = value;
        }
      }
    }
    if (!body.rows.length) throw new Error("表示できるデータがありません。");
    status.textContent = "CSVのスナップショットを表示しています（各側最大20件）。";
    table.hidden = false;
  } catch (error) {
    body.replaceChildren();
    status.textContent = error.message;
  }
});

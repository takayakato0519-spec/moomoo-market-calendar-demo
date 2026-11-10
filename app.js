"use strict";

const data = window.MARKET_CALENDAR;
const events = data.events;
const sourceDay = events.find((event) => event.date >= data.updatedAt.slice(0, 10))?.date
  ?? data.coverage[0];
const sourceMonth = sourceDay.slice(0, 7);
const byId = (id) => document.getElementById(id);
let month = sourceMonth;
let selected = sourceDay;
const keyFor = (year, monthIndex, day) => [year, monthIndex + 1, day].map((part) => String(part).padStart(2, "0")).join("-");

function renderEvents() {
  byId("selected").textContent = selected.replace(/^(\d+)-(\d+)-(\d+)$/, (_, y, m, d) => y + "年" + Number(m) + "月" + Number(d) + "日");
  const list = events.filter((event) => event.date === selected && matchesCategory(event));
  byId("events").replaceChildren();
  if (!list.length) {
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = "収録している発表予定はありません。";
    byId("events").append(empty);
  }
  for (const event of list) {
    const article = document.createElement("article");
    const meta = document.createElement("p");
    meta.className = "event-meta";
    meta.textContent = [event.time, event.region, event.category].join(" · ");
    const title = document.createElement("h3");
    title.textContent = event.title;
    const detail = document.createElement("p");
    detail.className = "note";
    detail.textContent = event.detail;
    const source = document.createElement("a");
    source.className = "note";
    source.href = event.url;
    source.textContent = "出典";
    article.append(meta, title, detail, source);
    byId("events").append(article);
  }
}

function matchesCategory(event) {
  const category = byId("category").value;
  return category === "all" || event.category === category;
}

function renderCalendar() {
  const [year, monthNumber] = month.split("-").map(Number);
  const monthIndex = monthNumber - 1;
  byId("month").textContent = year + "年 " + monthNumber + "月";
  const grid = byId("calendar");
  grid.replaceChildren();
  const offset = (new Date(year, monthIndex, 1).getDay() + 6) % 7;
  for (let blank = 0; blank < offset; blank++) grid.append(document.createElement("span"));
  const days = new Date(year, monthNumber, 0).getDate();
  for (let day = 1; day <= days; day++) {
    const date = keyFor(year, monthIndex, day);
    const count = events.filter((event) => event.date === date && matchesCategory(event)).length;
    const button = document.createElement("button");
    button.className = "day";
    button.dataset.date = date;
    button.setAttribute("aria-label", date + "、イベント" + count + "件");
    button.setAttribute("aria-pressed", String(date === selected));
    button.textContent = day;
    if (count) {
      const badge = document.createElement("small");
      badge.textContent = count + "件";
      button.append(badge);
    }
    button.addEventListener("click", () => {
      grid.querySelector('[aria-pressed="true"]')?.setAttribute("aria-pressed", "false");
      button.setAttribute("aria-pressed", "true");
      selected = date;
      renderEvents();
    });
    grid.append(button);
  }
  renderEvents();
}

function moveMonth(delta) {
  const [year, m] = month.split("-").map(Number);
  const date = new Date(year, m - 1 + delta, 1);
  selected = keyFor(date.getFullYear(), date.getMonth(), 1);
  month = selected.slice(0, 7);
  renderCalendar();
}

byId("prev").addEventListener("click", () => moveMonth(-1));
byId("next").addEventListener("click", () => moveMonth(1));
byId("reset").addEventListener("click", () => { month = sourceMonth; selected = sourceDay; renderCalendar(); });
renderCalendar();

byId("category").addEventListener("change", renderCalendar);
byId("updated").textContent = "更新 " + data.updatedAt.slice(0, 10) + " · JST";
byId("coverage").textContent = data.coverage.join(" ～ ");
if (data.licensedData) {
  byId("earnings-option").disabled = false;
  byId("licensed-status").textContent = "決算予定とアナリスト集計はFinnhubの対象7銘柄です。";
}
for (const row of data.analystTrends) {
  const line = document.createElement("p");
  line.textContent = [row.symbol, row.period, "強い買い " + row.strongBuy, "買い " + row.buy,
    "中立 " + row.hold, "売り " + row.sell, "強い売り " + row.strongSell].join(" · ");
  byId("analysts").append(line);
}

for (const item of data.news ?? []) {
  const row = document.createElement("article");
  const stamp = document.createElement("time");
  stamp.dateTime = item.date;
  stamp.textContent = item.date.slice(0, 10) + " · FRB";
  const title = document.createElement("h3");
  const source = document.createElement("a");
  source.href = item.url;
  source.textContent = item.title;
  title.append(source);
  row.append(stamp, title);
  byId("news").append(row);
}

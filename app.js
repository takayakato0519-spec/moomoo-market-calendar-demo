"use strict";

const sourceMonth = "2026-11";
const sourceDay = "2026-11-10";
// BLS November 2026 release calendar, checked November 11, 2026.
// Eastern Standard Time (UTC-5) converted to JST (UTC+9).
const events = [
  { date: "2026-11-04", time: "00:00", region: "米国", title: "求人労働異動調査（JOLTS）", detail: "2026年9月分" },
  { date: "2026-11-06", time: "22:30", region: "米国", title: "雇用統計", detail: "2026年10月分" },
  { date: sourceDay, time: "22:30", region: "米国", title: "消費者物価指数（CPI）", detail: "2026年10月分" },
  { date: sourceDay, time: "22:30", region: "米国", title: "実質賃金", detail: "2026年10月分" },
  { date: "2026-11-13", time: "22:30", region: "米国", title: "生産者物価指数（PPI）", detail: "2026年10月分" },
  { date: "2026-11-17", time: "22:30", region: "米国", title: "輸出入物価指数", detail: "2026年10月分" },
];
const byId = (id) => document.getElementById(id);
let month = sourceMonth;
let selected = sourceDay;
const keyFor = (year, monthIndex, day) => [year, monthIndex + 1, day].map((part) => String(part).padStart(2, "0")).join("-");

function renderEvents() {
  byId("selected").textContent = selected.replace(/^(\d+)-(\d+)-(\d+)$/, (_, y, m, d) => y + "年" + Number(m) + "月" + Number(d) + "日");
  const list = events.filter((event) => event.date === selected);
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
    meta.textContent = [event.time, event.region, "経済指標"].join(" · ");
    const title = document.createElement("h3");
    title.textContent = event.title;
    const detail = document.createElement("p");
    detail.className = "note";
    detail.textContent = event.detail;
    article.append(meta, title, detail);
    byId("events").append(article);
  }
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
    const count = events.filter((event) => event.date === date).length;
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

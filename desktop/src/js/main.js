/**
 * Dashboard logic: load the unified portfolio from the backend and render it.
 *
 * The whole page comes from one call, GET /api/v1/portfolio. Filtering and sorting
 * happen in the browser.
 */

import { apiGet, backendUrl } from "./api.js";
import { esc, money, pct, pnlClass, qty, signedMoney } from "./format.js";

const $ = (sel) => document.querySelector(sel);

const state = {
  summary: null,
  allocationKey: "by_asset_class",
  groupFilter: null, // group id or null
  accountFilter: "", // account id or ""
  search: "",
  sort: { key: "market_value_base", dir: -1 },
};

// ---------------------------------------------------------------------------------------
// Loading
// ---------------------------------------------------------------------------------------

async function load() {
  const btn = $("#refresh-btn");
  btn.disabled = true;
  try {
    state.summary = await apiGet("/api/v1/portfolio");
    setBackendStatus(true);
    hideError();
    render();
  } catch (err) {
    setBackendStatus(false);
    showError(String(err?.message ?? err));
  } finally {
    btn.disabled = false;
  }
}

async function setBackendStatus(ok) {
  const url = await backendUrl();
  $("#backend-status").className = `dot ${ok ? "dot-ok" : "dot-bad"}`;
  $("#backend-label").textContent = `Backend: ${url} — ${ok ? "connected" : "unreachable"}`;
}

function showError(message) {
  const el = $("#error-banner");
  el.textContent = message;
  el.hidden = false;
}

function hideError() {
  $("#error-banner").hidden = true;
}

// ---------------------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------------------

function render() {
  const s = state.summary;
  if (!s) return;
  renderHeader(s);
  renderKpis(s);
  renderAccounts(s);
  renderAllocation(s);
  renderFilters(s);
  renderPositions(s);
}

function renderHeader(s) {
  $("#as-of").textContent = `As of ${new Date(s.as_of).toLocaleString()} · ${s.base_currency}`;
  $("#simulated-badge").hidden = !s.brokers.some((b) => b.is_simulated);

  if (s.errors.length) {
    showError(s.errors.map((e) => `${e.broker_id}: ${e.message}`).join(" · "));
  }
}

function renderKpis(s) {
  const t = s.totals;
  const ccy = s.base_currency;
  $("#kpi-netliq").textContent = money(t.net_liquidation, ccy);
  $("#kpi-positions").textContent = money(t.positions_value, ccy);
  $("#kpi-cash").textContent = money(t.cash, ccy);

  const pnl = $("#kpi-pnl");
  pnl.textContent = signedMoney(t.unrealized_pnl, ccy);
  pnl.className = `kpi-value ${pnlClass(t.unrealized_pnl)}`;
  const pnlPct = $("#kpi-pnl-pct");
  pnlPct.textContent = `${pct(t.unrealized_pnl_pct, { signed: true })} on cost`;
  pnlPct.className = `kpi-sub ${pnlClass(t.unrealized_pnl)}`;
}

function renderAccounts(s) {
  const ccy = s.base_currency;
  $("#accounts-caption").textContent =
    `${s.accounts.length} accounts · ${s.brokers.length} brokers`;

  $("#accounts-list").innerHTML = s.accounts
    .map(
      (a) => `
      <div class="row clickable ${state.accountFilter === a.account.id ? "selected" : ""}"
           data-account="${esc(a.account.id)}">
        <div class="row-main">
          <div class="row-title">${esc(a.account.name)}
            <span class="tag">${esc(a.account.account_type)}</span>
            <span class="tag">${esc(a.account.currency)}</span>
          </div>
          <div class="row-sub muted">${esc(a.broker_name)} · ${a.position_count} positions ·
            cash ${money(a.cash, ccy, { compact: true })}</div>
          ${bar(a.weight)}
        </div>
        <div class="row-figures">
          <div class="strong">${money(a.net_liquidation, ccy)}</div>
          <div class="small ${pnlClass(a.unrealized_pnl)}">${signedMoney(a.unrealized_pnl, ccy)}</div>
          <div class="small muted">${pct(a.weight)}</div>
        </div>
      </div>`,
    )
    .join("");

  for (const el of document.querySelectorAll("#accounts-list [data-account]")) {
    el.addEventListener("click", () => {
      const id = el.dataset.account;
      state.accountFilter = state.accountFilter === id ? "" : id;
      render();
    });
  }
}

function renderAllocation(s) {
  const ccy = s.base_currency;
  const slices = s[state.allocationKey] ?? [];
  const max = Math.max(...slices.map((x) => Math.abs(x.weight)), 0.0001);

  $("#allocation-note").hidden = state.allocationKey !== "groups";
  $("#allocation-list").innerHTML = slices
    .slice(0, 12)
    .map(
      (x) => `
      <div class="row">
        <div class="row-main">
          <div class="row-title">
            ${x.color ? `<span class="swatch" style="background:${esc(x.color)}"></span>` : ""}
            ${esc(state.allocationKey === "by_symbol" ? x.key : x.label)}
            ${state.allocationKey === "by_symbol" ? `<span class="muted small">${esc(x.label)}</span>` : ""}
          </div>
          ${bar(x.weight / max, x.color)}
        </div>
        <div class="row-figures">
          <div class="strong">${money(x.market_value, ccy)}</div>
          <div class="small muted">${pct(x.weight)}${x.position_count ? ` · ${x.position_count} pos` : ""}</div>
        </div>
      </div>`,
    )
    .join("");
}

function renderFilters(s) {
  // Account dropdown
  const select = $("#account-filter");
  select.innerHTML =
    `<option value="">All accounts</option>` +
    s.accounts
      .map((a) => `<option value="${esc(a.account.id)}">${esc(a.broker_name)} · ${esc(a.account.name)}</option>`)
      .join("");
  select.value = state.accountFilter;

  // Group chips
  const groups = s.groups;
  $("#group-chips").innerHTML =
    `<button type="button" class="chip ${state.groupFilter === null ? "active" : ""}" data-group="">All</button>` +
    groups
      .map(
        (g) => `
        <button type="button" class="chip ${state.groupFilter === g.key ? "active" : ""}" data-group="${esc(g.key)}">
          <span class="swatch" style="background:${esc(g.color ?? "#888")}"></span>${esc(g.label)}
          <span class="muted">${g.position_count}</span>
        </button>`,
      )
      .join("");

  for (const el of document.querySelectorAll("#group-chips [data-group]")) {
    el.addEventListener("click", () => {
      state.groupFilter = el.dataset.group || null;
      render();
    });
  }
}

function renderPositions(s) {
  const ccy = s.base_currency;
  const accountNames = Object.fromEntries(s.accounts.map((a) => [a.account.id, a]));
  const groupColors = Object.fromEntries(s.groups.map((g) => [g.key, g]));
  const q = state.search.trim().toLowerCase();

  let rows = s.positions.filter(
    (p) =>
      (!state.accountFilter || p.account_id === state.accountFilter) &&
      (!state.groupFilter || p.group_ids.includes(state.groupFilter)) &&
      (!q || p.symbol.toLowerCase().includes(q) || p.name.toLowerCase().includes(q)),
  );

  const { key, dir } = state.sort;
  rows = rows.toSorted((a, b) => {
    const x = a[key];
    const y = b[key];
    return (typeof x === "string" ? x.localeCompare(y) : x - y) * dir;
  });

  const total = rows.reduce((acc, p) => acc + p.market_value_base, 0);
  $("#positions-count").textContent = `${rows.length} · ${money(total, ccy)}`;

  for (const th of document.querySelectorAll("#positions-table th[data-sort]")) {
    th.classList.toggle("sorted", th.dataset.sort === key);
    th.dataset.dir = th.dataset.sort === key ? (dir > 0 ? "asc" : "desc") : "";
  }

  $("#positions-table tbody").innerHTML = rows.length
    ? rows
        .map((p) => {
          const acct = accountNames[p.account_id];
          const dots = p.group_ids
            .map((g) => groupColors[g])
            .filter(Boolean)
            .map((g) => `<span class="swatch" title="${esc(g.label)}" style="background:${esc(g.color)}"></span>`)
            .join("");
          return `
          <tr>
            <td><div class="strong">${esc(p.option ? p.option.underlying : p.symbol)}</div>
                <div class="small muted">${esc(p.name)}</div></td>
            <td><div>${esc(acct?.broker_name ?? p.broker_id)}</div>
                <div class="small muted">${esc(acct?.account.name ?? p.account_id)}</div></td>
            <td><span class="tag">${esc(p.asset_class)}</span></td>
            <td class="num">${qty(p.quantity)}${p.multiplier !== 1 ? `<span class="muted small"> ×${p.multiplier}</span>` : ""}</td>
            <td class="num">${money(p.average_cost, p.currency)}</td>
            <td class="num">${money(p.market_price, p.currency)}</td>
            <td class="num"><div class="strong">${money(p.market_value_base, ccy)}</div>
                ${p.currency !== ccy ? `<div class="small muted">${money(p.market_value, p.currency)}</div>` : ""}</td>
            <td class="num ${pnlClass(p.unrealized_pnl_base)}">
                <div>${signedMoney(p.unrealized_pnl_base, ccy)}</div>
                <div class="small">${pct(p.unrealized_pnl_pct, { signed: true })}</div></td>
            <td class="num">${pct(p.weight)}</td>
            <td>${dots}</td>
          </tr>`;
        })
        .join("")
    : `<tr><td colspan="10" class="empty muted">No positions match the current filters.</td></tr>`;
}

/** A small horizontal bar for weights (0..1). */
function bar(fraction, color) {
  const w = Math.max(0, Math.min(1, fraction)) * 100;
  const style = color ? `width:${w}%;background:${color}` : `width:${w}%`;
  return `<div class="bar"><div class="bar-fill" style="${esc(style)}"></div></div>`;
}

// ---------------------------------------------------------------------------------------
// Event wiring
// ---------------------------------------------------------------------------------------

function wire() {
  $("#refresh-btn").addEventListener("click", load);

  for (const tab of document.querySelectorAll("#allocation-tabs .tab")) {
    tab.addEventListener("click", () => {
      state.allocationKey = tab.dataset.key;
      for (const t of document.querySelectorAll("#allocation-tabs .tab")) {
        t.classList.toggle("active", t === tab);
      }
      if (state.summary) renderAllocation(state.summary);
    });
  }

  $("#search").addEventListener("input", (e) => {
    state.search = e.target.value;
    if (state.summary) renderPositions(state.summary);
  });

  $("#account-filter").addEventListener("change", (e) => {
    state.accountFilter = e.target.value;
    render();
  });

  for (const th of document.querySelectorAll("#positions-table th[data-sort]")) {
    th.addEventListener("click", () => {
      const key = th.dataset.sort;
      state.sort = state.sort.key === key ? { key, dir: -state.sort.dir } : { key, dir: -1 };
      if (state.summary) renderPositions(state.summary);
    });
  }
}

wire();
load();

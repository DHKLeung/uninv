/**
 * uninv - Unified Investing Dashboard
 *
 * Consumes unified backend snapshot (/api/v1/snapshot) and live FX rates (/api/v1/fx).
 */

import { apiGet, backendUrl } from "./api.js";
import {
  esc,
  formatMoney,
  formatPct,
  formatQty,
  formatSignedMoney,
  pnlClass,
  setFxRate,
} from "./format.js";

const $ = (sel) => document.querySelector(sel);

const state = {
  brokers: [],
  snapshots: [], // list of BrokerAccountSnapshot objects
  selectedAccount: "", // empty for "All", or account_id
  search: "",
  currency: "USD",
  asof: null,
  sort: { key: "market_value", dir: -1 },
};

// ---------------------------------------------------------------------------------------
// Data Loading
// ---------------------------------------------------------------------------------------

async function load() {
  const btn = $("#refresh-btn");
  btn.disabled = true;
  btn.textContent = "Loading…";

  try {
    // 1. Fetch supporting brokers
    const brokers = await apiGet("/api/v1/supporting-brokers");
    state.brokers = brokers;

    // 2. Fetch accounts for each broker
    const brokerMap = Object.fromEntries(brokers.map((b) => [b.id, b.name]));
    const accountPromises = brokers.map((b) =>
      apiGet(`/api/v1/accounts?broker_id=${encodeURIComponent(b.id)}`)
    );
    const accountResponses = await Promise.all(accountPromises);

    // 3. Fetch unified snapshots for each account
    const snapshotPromises = [];
    for (const resp of accountResponses) {
      if (resp.asof) {
        state.asof = resp.asof;
      }
      for (const acctId of resp.accounts) {
        snapshotPromises.push(
          apiGet(
            `/api/v1/snapshot?broker_id=${encodeURIComponent(resp.broker_id)}&account_id=${encodeURIComponent(acctId)}`
          ).then((snap) => ({
            ...snap,
            broker_name: brokerMap[snap.broker_id] ?? snap.broker_id,
          }))
        );
      }
    }

    state.snapshots = await Promise.all(snapshotPromises);

    // 4. Update FX rate for selected currency if non-USD
    if (state.currency !== "USD") {
      try {
        const fx = await apiGet(`/api/v1/fx?base=USD&quote=${encodeURIComponent(state.currency)}`);
        setFxRate(state.currency, fx.rate);
      } catch (e) {
        console.warn("Could not refresh live FX rate:", e);
      }
    }

    setBackendStatus(true);
    hideError();
    render();
  } catch (err) {
    setBackendStatus(false);
    showError(String(err?.message ?? err));
  } finally {
    btn.disabled = false;
    btn.textContent = "Refresh";
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
  renderHeader();
  renderKpis();
  renderAccounts();
  renderFilterPills();
  renderPositions();
  renderCashBalances();
}

function renderHeader() {
  if (state.asof) {
    const dt = new Date(state.asof);
    const formattedDate = dt.toLocaleString("en-GB", {
      dateStyle: "medium",
      timeStyle: "medium",
    });
    $("#as-of").textContent = `As of ${formattedDate} UTC`;
  }
  $("#currency-select").value = state.currency;
}

function getFilteredSnapshots() {
  if (!state.selectedAccount) {
    return state.snapshots;
  }
  return state.snapshots.filter((s) => s.account_id === state.selectedAccount);
}

function getAllFilteredPositions() {
  const filteredSnaps = getFilteredSnapshots();
  return filteredSnaps.flatMap((s) =>
    s.positions.map((p) => ({
      ...p,
      broker_id: s.broker_id,
      broker_name: s.broker_name,
      account_id: s.account_id,
    }))
  );
}

function renderKpis() {
  const ccy = state.currency;
  const filteredSnaps = getFilteredSnapshots();

  const netLiqUsd = filteredSnaps.reduce((acc, s) => acc + (s.account_values?.net_liquidation ?? 0), 0);
  const positionValUsd = filteredSnaps.reduce((acc, s) => acc + (s.account_values?.gross_position_value ?? 0), 0);
  const cashValUsd = filteredSnaps.reduce((acc, s) => acc + (s.account_values?.cash_balance ?? 0), 0);
  const totalUnrealizedPnlUsd = filteredSnaps.reduce((acc, s) => acc + (s.account_values?.unrealized_pnl ?? 0), 0);
  const availFundsUsd = filteredSnaps.reduce((acc, s) => acc + (s.account_values?.available_funds ?? 0), 0);
  const buyingPowerUsd = filteredSnaps.reduce((acc, s) => acc + (s.account_values?.buying_power ?? 0), 0);

  const totalPositions = getAllFilteredPositions();
  const totalCostBasis = totalPositions.reduce((acc, p) => acc + (p.cost_basis ?? 0), 0);
  const totalPnlPct = totalCostBasis !== 0 ? totalUnrealizedPnlUsd / Math.abs(totalCostBasis) : 0;

  $("#kpi-netliq").textContent = formatMoney(netLiqUsd, ccy);
  $("#kpi-positions").textContent = formatMoney(positionValUsd, ccy);
  $("#kpi-cash").textContent = formatMoney(cashValUsd, ccy);

  const pnlEl = $("#kpi-pnl");
  pnlEl.textContent = formatSignedMoney(totalUnrealizedPnlUsd, ccy);
  pnlEl.className = `kpi-value ${pnlClass(totalUnrealizedPnlUsd)}`;

  const pnlPctEl = $("#kpi-pnl-pct");
  pnlPctEl.textContent = formatPct(totalPnlPct, { signed: true });
  pnlPctEl.className = `kpi-sub ${pnlClass(totalUnrealizedPnlUsd)}`;

  $("#kpi-avail").textContent = formatMoney(availFundsUsd, ccy);
  $("#kpi-buyingpower").textContent = formatMoney(buyingPowerUsd, ccy);
}

function renderAccounts() {
  const ccy = state.currency;
  $("#accounts-caption").textContent = `${state.snapshots.length} accounts · ${state.brokers.length} broker(s)`;

  const grid = $("#accounts-grid");
  grid.innerHTML = state.snapshots
    .map((s) => {
      const isSelected = state.selectedAccount === s.account_id;
      const av = s.account_values;
      const posCount = s.positions?.length ?? 0;
      const pnlPct = av.gross_position_value !== 0 ? av.unrealized_pnl / Math.abs(av.gross_position_value) : 0;

      return `
      <div class="account-card ${isSelected ? "selected" : ""}" data-account="${esc(s.account_id)}">
        <div class="account-card-header">
          <div class="account-alias">${esc(s.account_id)}</div>
          <div class="account-badge">${esc(s.broker_name)}</div>
        </div>
        <div class="account-number muted">${esc(s.account_id)} · ${posCount} positions</div>
        <div class="account-metrics-grid">
          <div>
            <div class="metric-label">NET LIQUIDATION VALUE</div>
            <div class="metric-value font-mono strong">${formatMoney(av.net_liquidation, ccy)}</div>
          </div>
          <div class="text-right">
            <div class="metric-label">POSITION VALUE</div>
            <div class="metric-value font-mono">${formatMoney(av.gross_position_value, ccy)}</div>
          </div>
          <div>
            <div class="metric-label">CASH BALANCE</div>
            <div class="metric-value font-mono ${pnlClass(av.cash_balance)}">${formatMoney(av.cash_balance, ccy)}</div>
          </div>
          <div class="text-right">
            <div class="metric-label">UNREALISED P&amp;L</div>
            <div class="metric-value font-mono ${pnlClass(av.unrealized_pnl)}">
              ${formatSignedMoney(av.unrealized_pnl, ccy)}
              <span class="metric-pct">(${formatPct(pnlPct, { signed: true })})</span>
            </div>
          </div>
        </div>
      </div>`;
    })
    .join("");

  for (const card of grid.querySelectorAll(".account-card")) {
    card.addEventListener("click", () => {
      const id = card.dataset.account;
      state.selectedAccount = state.selectedAccount === id ? "" : id;
      renderFilterPills();
      renderAccounts();
      renderKpis();
      renderPositions();
      renderCashBalances();
    });
  }
}

function renderFilterPills() {
  const pillsContainer = $("#account-filter-pills");
  let pillsHtml = `
    <button type="button" class="filter-pill ${state.selectedAccount === "" ? "active" : ""}" data-filter="">
      All Accounts
    </button>`;

  pillsHtml += state.snapshots
    .map(
      (s) => `
      <button type="button" class="filter-pill ${state.selectedAccount === s.account_id ? "active" : ""}" data-filter="${esc(s.account_id)}">
        ${esc(s.broker_name)} (${esc(s.account_id)})
      </button>`
    )
    .join("");

  pillsContainer.innerHTML = pillsHtml;

  for (const btn of pillsContainer.querySelectorAll(".filter-pill")) {
    btn.addEventListener("click", () => {
      state.selectedAccount = btn.dataset.filter;
      renderFilterPills();
      renderAccounts();
      renderKpis();
      renderPositions();
      renderCashBalances();
    });
  }
}

function renderCashBalances() {
  const ccy = state.currency;
  const filteredSnaps = getFilteredSnapshots();

  const allCashItems = filteredSnaps.flatMap((s) =>
    (s.account_values?.cash_balances ?? []).map((cb) => ({
      account_id: s.account_id,
      broker_name: s.broker_name,
      currency: cb.currency,
      amount: cb.amount,
    }))
  );

  const totalCashUsd = filteredSnaps.reduce(
    (acc, s) => acc + (s.account_values?.cash_balance ?? 0.0),
    0
  );

  $("#cash-balances-caption").textContent = `${filteredSnaps.length} ${
    filteredSnaps.length === 1 ? "account" : "accounts"
  } · ${formatMoney(totalCashUsd, ccy)} total cash`;

  const tbody = $("#cash-table tbody");
  tbody.innerHTML = allCashItems.length
    ? allCashItems
        .map((c) => {
          return `
          <tr>
            <td>
              <span class="account-tag">${esc(c.account_id)}</span>
            </td>
            <td>
              <span class="broker-name">${esc(c.broker_name)}</span>
            </td>
            <td class="num">
              <span class="currency-badge">${esc(c.currency)}</span>
            </td>
            <td class="num font-mono strong ${pnlClass(c.amount)}">
              ${formatMoney(c.amount, c.currency)}
            </td>
            <td class="num font-mono strong ${pnlClass(c.amount)}">
              ${formatMoney(c.amount, ccy)}
            </td>
          </tr>`;
        })
        .join("")
    : `<tr><td colspan="5" class="empty muted">No cash balances available.</td></tr>`;
}

function renderPositions() {
  const ccy = state.currency;
  const q = state.search.trim().toLowerCase();

  let rows = getAllFilteredPositions().filter((p) => {
    if (!q) return true;
    return (
      (p.symbol && p.symbol.toLowerCase().includes(q)) ||
      (p.instrument && p.instrument.toLowerCase().includes(q)) ||
      (p.sec_type && p.sec_type.toLowerCase().includes(q)) ||
      (p.exchange && p.exchange.toLowerCase().includes(q))
    );
  });

  const { key, dir } = state.sort;
  rows = rows.toSorted((a, b) => {
    let x = a[key];
    let y = b[key];
    if (x === null || x === undefined) x = "";
    if (y === null || y === undefined) y = "";
    if (typeof x === "number" && typeof y === "number") {
      return (x - y) * dir;
    }
    return String(x).localeCompare(String(y)) * dir;
  });

  const totalFilteredValueUsd = rows.reduce((acc, p) => acc + (p.market_value ?? 0), 0);
  $("#positions-count").textContent = `${rows.length} positions · ${formatMoney(totalFilteredValueUsd, ccy)}`;

  for (const th of document.querySelectorAll("#positions-table th[data-sort]")) {
    th.classList.toggle("sorted", th.dataset.sort === key);
    th.dataset.dir = th.dataset.sort === key ? (dir > 0 ? "asc" : "desc") : "";
  }

  const tbody = $("#positions-table tbody");
  tbody.innerHTML = rows.length
    ? rows
        .map((p) => {
          const expiry = p.last_trade_date ? esc(p.last_trade_date) : '<span class="muted">—</span>';
          const secType = p.sec_type || "STOCKS";
          const secClass = secType.toLowerCase();
          const exchangeBadge = p.exchange ? `<span class="exchange-badge">${esc(p.exchange)}</span>` : '<span class="muted">—</span>';
          const pnlPct = p.cost_basis !== 0 ? (p.unrealized_pnl ?? 0) / Math.abs(p.cost_basis) : 0;

          return `
          <tr>
            <td>
              <div class="instrument-name">${esc(p.instrument)}</div>
            </td>
            <td>
              <span class="symbol-code">${esc(p.symbol)}</span>
            </td>
            <td>
              <span class="sec-badge ${esc(secClass)}">${esc(secType)}</span>
            </td>
            <td>${exchangeBadge}</td>
            <td>${expiry}</td>
            <td class="num font-mono">${formatQty(p.position)}</td>
            <td class="num font-mono">${formatMoney(p.avg_price, ccy)}</td>
            <td class="num font-mono">${formatMoney(p.mark_price, ccy)}</td>
            <td class="num font-mono">${formatMoney(p.cost_basis, ccy)}</td>
            <td class="num font-mono strong">${formatMoney(p.market_value, ccy)}</td>
            <td class="num"><span class="currency-badge">${esc(p.currency)}</span></td>
            <td class="num font-mono ${pnlClass(p.unrealized_pnl)}">
              ${
                p.unrealized_pnl != null
                  ? `<div>${formatSignedMoney(p.unrealized_pnl, ccy)}</div>
                     <div class="small-pct">${formatPct(pnlPct, { signed: true })}</div>`
                  : '<span class="muted">—</span>'
              }
            </td>
          </tr>`;
        })
        .join("")
    : `<tr><td colspan="12" class="empty muted">No positions match the current account or search filter.</td></tr>`;
}

// ---------------------------------------------------------------------------------------
// Event Wiring
// ---------------------------------------------------------------------------------------

function wireEvents() {
  $("#refresh-btn").addEventListener("click", load);

  $("#currency-select").addEventListener("change", async (e) => {
    state.currency = e.target.value;
    if (state.currency !== "USD") {
      try {
        const fx = await apiGet(`/api/v1/fx?base=USD&quote=${encodeURIComponent(state.currency)}`);
        setFxRate(state.currency, fx.rate);
      } catch (err) {
        console.warn("Could not load FX rate:", err);
      }
    }
    render();
  });

  $("#search").addEventListener("input", (e) => {
    state.search = e.target.value;
    renderPositions();
  });

  for (const th of document.querySelectorAll("#positions-table th[data-sort]")) {
    th.addEventListener("click", () => {
      const key = th.dataset.sort;
      state.sort = state.sort.key === key ? { key, dir: -state.sort.dir } : { key, dir: -1 };
      renderPositions();
    });
  }
}

wireEvents();
load();

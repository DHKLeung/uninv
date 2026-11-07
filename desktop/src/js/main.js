/**
 * uninv - Unified Investing Dashboard
 *
 * Multi-account, multi-broker positions viewer supporting USD and GBP display.
 */

import { apiGet, backendUrl } from "./api.js";
import { esc, formatMoney, formatPct, formatQty, formatSignedMoney, pnlClass } from "./format.js";

const $ = (sel) => document.querySelector(sel);

const state = {
  brokers: [],
  accounts: [], // [{ account_id, broker_id, alias, broker_name }]
  cashBalances: {}, // { [account_id]: cash_balance_usd }
  positions: [],
  selectedAccount: "", // empty for "All", or account_id
  search: "",
  currency: "USD",
  lastUpdated: null,
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
    // 1. Fetch brokers
    const brokers = await apiGet("/api/v1/brokers");
    state.brokers = brokers;

    // 2. Fetch accounts for each broker concurrently
    const brokerMap = Object.fromEntries(brokers.map((b) => [b.id, b.name]));
    const accountPromises = brokers.map((b) => apiGet(`/api/v1/accounts/${b.id}`));
    const accountsNested = await Promise.all(accountPromises);

    const allAccounts = accountsNested.flat().map((acct) => ({
      ...acct,
      broker_name: brokerMap[acct.broker_id] ?? acct.broker_id,
    }));
    state.accounts = allAccounts;

    const accountAliasMap = Object.fromEntries(allAccounts.map((a) => [a.account_id, a.alias]));

    // 3. Fetch cash balances for each broker concurrently
    const cashPromises = brokers.map((b) => apiGet(`/api/v1/cash-balance/${b.id}`));
    const cashNested = await Promise.all(cashPromises);
    const allCash = cashNested.flat();
    state.cashBalances = Object.fromEntries(
      allCash.map((c) => [c.account_id, c.cash_balance])
    );

    // 4. Fetch positions for each broker concurrently
    const positionPromises = brokers.map((b) => apiGet(`/api/v1/positions/${b.id}`));
    const positionsNested = await Promise.all(positionPromises);

    state.positions = positionsNested.flat().map((p) => {
      const mult = p.multiplier ?? 1.0;
      const marketValue = p.market_value != null
        ? p.market_value
        : (p.position ?? 0) * (p.mark_price ?? 0) * mult;
      const costBasis = p.cost_basis != null
        ? p.cost_basis
        : (p.average_price != null ? (p.position ?? 0) * p.average_price * mult : null);
      const unrealisedPnl = costBasis != null ? marketValue - costBasis : null;
      const unrealisedPnlPct = costBasis != null && costBasis !== 0
        ? unrealisedPnl / Math.abs(costBasis)
        : null;

      return {
        ...p,
        account_alias: accountAliasMap[p.account_id] ?? p.account_id,
        multiplier: mult,
        market_value: marketValue,
        cost_basis: costBasis,
        unrealised_pnl: unrealisedPnl,
        unrealised_pnl_pct: unrealisedPnlPct,
      };
    });

    state.lastUpdated = new Date();
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
  if (state.lastUpdated) {
    const formattedDate = state.lastUpdated.toLocaleString("en-GB", {
      dateStyle: "medium",
      timeStyle: "short",
    });
    $("#as-of").textContent = `As of ${formattedDate}`;
  }
  $("#currency-select").value = state.currency;
}

function renderKpis() {
  const ccy = state.currency;

  const filteredPositions = !state.selectedAccount
    ? state.positions
    : state.positions.filter((p) => p.account_id === state.selectedAccount);

  const marketValUsd = filteredPositions.reduce((acc, p) => acc + (p.market_value ?? 0), 0);

  const cashValUsd = state.selectedAccount
    ? (state.cashBalances[state.selectedAccount] ?? 0.0)
    : Object.values(state.cashBalances).reduce((acc, val) => acc + val, 0);

  const netLiqUsd = marketValUsd + cashValUsd;

  const totalCostBasis = filteredPositions.reduce((acc, p) => acc + (p.cost_basis ?? 0), 0);
  const totalUnrealisedPnlUsd = filteredPositions.reduce((acc, p) => acc + (p.unrealised_pnl ?? 0), 0);
  const totalPnlPct = totalCostBasis !== 0 ? totalUnrealisedPnlUsd / Math.abs(totalCostBasis) : 0;

  // British English KPI displays
  $("#kpi-netliq").textContent = formatMoney(netLiqUsd, ccy);
  $("#kpi-positions").textContent = formatMoney(marketValUsd, ccy);
  $("#kpi-cash").textContent = formatMoney(cashValUsd, ccy);

  const pnlEl = $("#kpi-pnl");
  pnlEl.textContent = formatSignedMoney(totalUnrealisedPnlUsd, ccy);
  pnlEl.className = `kpi-value ${pnlClass(totalUnrealisedPnlUsd)}`;

  const pnlPctEl = $("#kpi-pnl-pct");
  pnlPctEl.textContent = formatPct(totalPnlPct, { signed: true });
  pnlPctEl.className = `kpi-sub ${pnlClass(totalUnrealisedPnlUsd)}`;
}

function renderAccounts() {
  const ccy = state.currency;
  $("#accounts-caption").textContent = `${state.accounts.length} accounts · ${state.brokers.length} brokers`;

  const grid = $("#accounts-grid");
  grid.innerHTML = state.accounts
    .map((acct) => {
      const acctPositions = state.positions.filter((p) => p.account_id === acct.account_id);
      const acctValUsd = acctPositions.reduce((acc, p) => acc + (p.market_value ?? 0), 0);
      const acctPnlUsd = acctPositions.reduce((acc, p) => acc + (p.unrealised_pnl ?? 0), 0);
      const acctCostBasis = acctPositions.reduce((acc, p) => acc + (p.cost_basis ?? 0), 0);
      const acctPnlPct = acctCostBasis !== 0 ? acctPnlUsd / Math.abs(acctCostBasis) : 0;
      const acctCashUsd = state.cashBalances[acct.account_id] ?? 0.0;
      const acctNetLiqUsd = acctValUsd + acctCashUsd;
      const isSelected = state.selectedAccount === acct.account_id;

      return `
      <div class="account-card ${isSelected ? "selected" : ""}" data-account="${esc(acct.account_id)}">
        <div class="account-card-header">
          <div class="account-alias">${esc(acct.alias)}</div>
          <div class="account-badge">${esc(acct.broker_name)}</div>
        </div>
        <div class="account-number muted">${esc(acct.account_id)} · ${acctPositions.length} positions</div>
        <div class="account-metrics-grid">
          <div>
            <div class="metric-label">NET LIQUIDATION VALUE</div>
            <div class="metric-value font-mono">${formatMoney(acctNetLiqUsd, ccy)}</div>
          </div>
          <div class="text-right">
            <div class="metric-label">POSITION VALUE</div>
            <div class="metric-value font-mono">${formatMoney(acctValUsd, ccy)}</div>
          </div>
          <div>
            <div class="metric-label">CASH BALANCE</div>
            <div class="metric-value font-mono ${pnlClass(acctCashUsd)}">${formatMoney(acctCashUsd, ccy)}</div>
          </div>
          <div class="text-right">
            <div class="metric-label">UNREALISED P&amp;L</div>
            <div class="metric-value font-mono ${pnlClass(acctPnlUsd)}">
              ${formatSignedMoney(acctPnlUsd, ccy)}
              <span class="metric-pct">(${formatPct(acctPnlPct, { signed: true })})</span>
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
      All
    </button>`;

  pillsHtml += state.accounts
    .map(
      (a) => `
      <button type="button" class="filter-pill ${state.selectedAccount === a.account_id ? "active" : ""}" data-filter="${esc(a.account_id)}">
        ${esc(a.alias)}
      </button>`,
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
  const filteredAccounts = !state.selectedAccount
    ? state.accounts
    : state.accounts.filter((a) => a.account_id === state.selectedAccount);

  const totalCashUsd = filteredAccounts.reduce(
    (acc, a) => acc + (state.cashBalances[a.account_id] ?? 0.0),
    0
  );

  $("#cash-balances-caption").textContent = `${filteredAccounts.length} ${
    filteredAccounts.length === 1 ? "account" : "accounts"
  } · ${formatMoney(totalCashUsd, ccy)} total cash`;

  const tbody = $("#cash-table tbody");
  tbody.innerHTML = filteredAccounts.length
    ? filteredAccounts
        .map((a) => {
          const cashUsd = state.cashBalances[a.account_id] ?? 0.0;
          return `
          <tr>
            <td>
              <span class="account-tag">${esc(a.alias)}</span>
            </td>
            <td>
              <span class="broker-name">${esc(a.broker_name)}</span>
            </td>
            <td>
              <span class="font-mono text-muted">${esc(a.account_id)}</span>
            </td>
            <td class="num">
              <span class="currency-badge">USD</span>
            </td>
            <td class="num font-mono strong ${pnlClass(cashUsd)}">
              ${formatMoney(cashUsd, ccy)}
            </td>
          </tr>`;
        })
        .join("")
    : `<tr><td colspan="5" class="empty muted">No cash accounts match the current filter.</td></tr>`;
}

function renderPositions() {
  const ccy = state.currency;
  const q = state.search.trim().toLowerCase();

  let rows = state.positions.filter((p) => {
    const matchAccount = !state.selectedAccount || p.account_id === state.selectedAccount;
    const matchSearch =
      !q ||
      p.symbol.toLowerCase().includes(q) ||
      p.instrument.toLowerCase().includes(q) ||
      p.account_alias.toLowerCase().includes(q);
    return matchAccount && matchSearch;
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

  const totalFilteredValueUsd = rows.reduce((acc, p) => acc + p.market_value, 0);
  $("#positions-count").textContent = `${rows.length} positions · ${formatMoney(totalFilteredValueUsd, ccy)}`;

  for (const th of document.querySelectorAll("#positions-table th[data-sort]")) {
    th.classList.toggle("sorted", th.dataset.sort === key);
    th.dataset.dir = th.dataset.sort === key ? (dir > 0 ? "asc" : "desc") : "";
  }

  const tbody = $("#positions-table tbody");
  tbody.innerHTML = rows.length
    ? rows
        .map((p) => {
          const expiry = p.expiry_date ? esc(p.expiry_date) : '<span class="muted">—</span>';
          const delivery = p.delivery_date ? esc(p.delivery_date) : '<span class="muted">—</span>';
          return `
          <tr>
            <td>
              <div class="instrument-name">${esc(p.instrument)}</div>
            </td>
            <td>
              <span class="symbol-code">${esc(p.symbol)}</span>
            </td>
            <td>
              <span class="account-tag">${esc(p.account_alias)}</span>
            </td>
            <td>${expiry}</td>
            <td>${delivery}</td>
            <td class="num font-mono">${formatQty(p.position)}</td>
            <td class="num font-mono">${formatMoney(p.average_price, ccy)}</td>
            <td class="num font-mono">${formatMoney(p.cost_basis, ccy)}</td>
            <td class="num font-mono">${formatMoney(p.mark_price, ccy)}</td>
            <td class="num font-mono strong">${formatMoney(p.market_value, ccy)}</td>
            <td class="num"><span class="currency-badge">${esc(p.currency)}</span></td>
            <td class="num font-mono ${pnlClass(p.unrealised_pnl)}">
              ${
                p.unrealised_pnl != null
                  ? `<div>${formatSignedMoney(p.unrealised_pnl, ccy)}</div>
                     <div class="small-pct">${formatPct(p.unrealised_pnl_pct, { signed: true })}</div>`
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

  $("#currency-select").addEventListener("change", (e) => {
    state.currency = e.target.value;
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

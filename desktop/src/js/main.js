/**
 * uninv - Unified Investing Dashboard
 *
 * Global Data Pulling:
 * All broker accounts, unified snapshots, and the complete FX matrix (/api/v1/fx)
 * are fetched globally on app load or when clicking Refresh.
 * The data is fixed in memory; currency switching is an instantaneous GUI calculation
 * using the pre-pulled FX matrix without making any additional network requests.
 *
 * Unidirectional Portfolio Interaction:
 * In the Portfolio page, Section 1 (Accounts horizontal tiles) is the sole selector.
 * Selecting an account triggers a single unidirectional reaction path:
 * Section 1 Tiles -> Section 2 Metrics Board -> Section 3 Positions & Cash Balances.
 */

import { apiGet, backendUrl } from "./api.js";
import {
  CURRENCY_SYMBOLS,
  convertAmount,
  esc,
  formatMoney,
  formatPct,
  formatQty,
  formatSignedMoney,
  pnlClass,
} from "./format.js";

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const state = {
  activePage: "portfolio",
  // Fixed Global Data Pulled Once
  brokers: [],
  currencies: [],
  snapshots: [], // list of BrokerAccountSnapshot objects
  fxMatrix: null, // nested map: rates[from][to] = rate
  asof: null,

  // Display / Interaction State
  selectedAccount: "", // empty for "All", or account_id string
  currency: "USD",
  search: "",
  sort: { key: "market_value", dir: -1 },
};

// ---------------------------------------------------------------------------------------
// Global Data Loading (Fixed In-Memory Snapshot & FX Matrix)
// ---------------------------------------------------------------------------------------

function syncCurrencyDropdown(currencies) {
  const select = $("#currency-select");
  if (!select || !Array.isArray(currencies) || currencies.length === 0) return;

  const existing = new Set(Array.from(select.options).map((o) => o.value));
  for (const c of currencies) {
    if (!existing.has(c)) {
      const opt = document.createElement("option");
      opt.value = c;
      const sym = CURRENCY_SYMBOLS[c] ? ` (${CURRENCY_SYMBOLS[c].trim()})` : "";
      opt.textContent = `${c}${sym}`;
      select.appendChild(opt);
    }
  }
}

/**
 * Global data refresh: pulls all broker data, account snapshots, and the full FX matrix.
 * All operations and page displays throughout the app consume this fixed in-memory data.
 */
async function load() {
  const btn = $("#refresh-btn");
  btn.disabled = true;
  btn.textContent = "Loading…";

  try {
    // 1. Fetch brokers and full FX matrix concurrently
    const [brokers, fxData] = await Promise.all([
      apiGet("/api/v1/supporting-brokers"),
      apiGet("/api/v1/fx"),
    ]);

    state.brokers = brokers;
    state.currencies = fxData.currencies || [];
    state.fxMatrix = fxData.rates || {};
    if (fxData.asof) {
      state.asof = fxData.asof;
    }

    // Sync currency dropdown with supported currencies from matrix
    syncCurrencyDropdown(state.currencies);

    // 2. Fetch accounts for each broker
    const brokerMap = Object.fromEntries(brokers.map((b) => [b.id, b.name]));
    const accountPromises = brokers.map((b) =>
      apiGet(`/api/v1/accounts?broker_id=${encodeURIComponent(b.id)}`)
    );
    const accountResponses = await Promise.all(accountPromises);

    // 3. Fetch snapshots for all managed accounts
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
  $("#backend-label").textContent = `Backend: ${ok ? "connected" : "unreachable"}`;
  $("#backend-label").title = `${url} (${ok ? "healthy" : "offline"})`;
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
// Rendering Pipeline
// ---------------------------------------------------------------------------------------

function render() {
  renderHeader();
  renderAccounts();
  renderMetrics();
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

// ---------------------------------------------------------------------------------------
// Section 1: Accounts Horizontal Tiles (Authoritative Selector)
// ---------------------------------------------------------------------------------------

function updateAccountTilesActiveState() {
  const listEl = $("#accounts-horizontal-list");
  if (!listEl) return;
  for (const tile of listEl.querySelectorAll(".account-tile")) {
    const acct = tile.dataset.account;
    tile.classList.toggle("active", acct === state.selectedAccount);
  }
}

/**
 * Unidirectional reaction path:
 * Selecting an account updates Section 1 tile highlight, then updates Section 2, then Section 3.
 */
function onSelectAccount(acctId) {
  if (state.selectedAccount === acctId && acctId !== "") {
    state.selectedAccount = "";
  } else {
    state.selectedAccount = acctId;
  }

  // 1. Update Section 1 tiles active state
  updateAccountTilesActiveState();
  // 2. Reactively update Section 2 Metrics Board
  renderMetrics();
  // 3. Reactively update Section 3 Holdings
  renderPositions();
  renderCashBalances();
}

function renderAccounts() {
  const ccy = state.currency;
  const listEl = $("#accounts-horizontal-list");
  if (!listEl) return;

  const totalAccounts = state.snapshots.length;
  $("#accounts-caption").textContent = `${totalAccounts} accounts · ${state.brokers.length} broker(s)`;

  // Tile 1: "All Accounts"
  const allNetLiqConverted = state.snapshots.reduce(
    (acc, s) =>
      acc +
      convertAmount(
        s.account_values?.net_liquidation ?? 0,
        s.account_values?.currency,
        ccy,
        state.fxMatrix
      ),
    0
  );

  const isAllActive = state.selectedAccount === "";
  let html = `
    <div class="account-tile ${isAllActive ? "active" : ""}" data-account="">
      <div class="account-tile-header">
        <span class="account-tile-name">All Accounts</span>
        <span class="account-tile-badge">Consolidated</span>
      </div>
      <div class="account-tile-body">
        <span class="account-tile-val font-mono">${formatMoney(allNetLiqConverted, ccy)}</span>
        <span class="account-tile-caption">${totalAccounts} accounts total</span>
      </div>
    </div>
  `;

  // Tile 2+: Individual Broker Accounts
  for (const s of state.snapshots) {
    const isActive = state.selectedAccount === s.account_id;
    const av = s.account_values;
    const acctNetLiq = convertAmount(av?.net_liquidation ?? 0, av?.currency, ccy, state.fxMatrix);
    const posCount = s.positions?.length ?? 0;
    const displayName =
      s.broker_id === "futu" && s.account_id.length > 6
        ? `...${s.account_id.slice(-4)}`
        : s.account_id;

    html += `
      <div class="account-tile ${isActive ? "active" : ""}" data-account="${esc(s.account_id)}">
        <div class="account-tile-header">
          <span class="account-tile-name">${esc(displayName)}</span>
          <span class="account-tile-badge">${esc(s.broker_name)}</span>
        </div>
        <div class="account-tile-body">
          <span class="account-tile-val font-mono">${formatMoney(acctNetLiq, ccy)}</span>
          <span class="account-tile-caption">${posCount} ${posCount === 1 ? "position" : "positions"}</span>
        </div>
      </div>
    `;
  }

  listEl.innerHTML = html;

  for (const tile of listEl.querySelectorAll(".account-tile")) {
    tile.addEventListener("click", () => {
      onSelectAccount(tile.dataset.account);
    });
  }
}

// ---------------------------------------------------------------------------------------
// Section 2: Metrics Board (Reflects Section 1 Selection)
// ---------------------------------------------------------------------------------------

function renderMetrics() {
  const ccy = state.currency;
  const filteredSnaps = getFilteredSnapshots();

  // Header Scope Description
  if (state.selectedAccount === "") {
    $("#metrics-scope-label").textContent = "ALL ACCOUNTS CONSOLIDATED";
    $("#metrics-scope-desc").textContent = `Aggregated across all ${state.snapshots.length} connected accounts`;
  } else {
    const snap = state.snapshots.find((s) => s.account_id === state.selectedAccount);
    const brokerName = snap?.broker_name || "Broker";
    const displayId =
      snap?.broker_id === "futu" && snap?.account_id.length > 6
        ? `...${snap.account_id.slice(-4)}`
        : state.selectedAccount;
    $("#metrics-scope-label").textContent = `ACCOUNT: ${displayId}`;
    $("#metrics-scope-desc").textContent = `${brokerName} account-level margin & balances`;
  }
  $("#metrics-currency-name").textContent = ccy;

  // Aggregate values using pre-pulled FX matrix
  const netLiq = filteredSnaps.reduce(
    (acc, s) =>
      acc +
      convertAmount(
        s.account_values?.net_liquidation ?? 0,
        s.account_values?.currency,
        ccy,
        state.fxMatrix
      ),
    0
  );

  const unrealizedPnl = filteredSnaps.reduce(
    (acc, s) =>
      acc +
      convertAmount(
        s.account_values?.unrealized_pnl ?? 0,
        s.account_values?.currency,
        ccy,
        state.fxMatrix
      ),
    0
  );

  const grossPositionVal = filteredSnaps.reduce(
    (acc, s) =>
      acc +
      convertAmount(
        s.account_values?.gross_position_value ?? 0,
        s.account_values?.currency,
        ccy,
        state.fxMatrix
      ),
    0
  );

  const excessLiq = filteredSnaps.reduce(
    (acc, s) =>
      acc +
      convertAmount(
        s.account_values?.excess_liquidity ?? 0,
        s.account_values?.currency,
        ccy,
        state.fxMatrix
      ),
    0
  );

  const maintMargin = filteredSnaps.reduce(
    (acc, s) =>
      acc +
      convertAmount(
        s.account_values?.maint_margin_req ?? 0,
        s.account_values?.currency,
        ccy,
        state.fxMatrix
      ),
    0
  );

  // Compute Unrealized PnL %
  const totalPositions = getAllFilteredPositions();
  const totalCostBasisConverted = totalPositions.reduce(
    (acc, p) =>
      acc + (p.cost_basis != null ? convertAmount(p.cost_basis, p.currency, ccy, state.fxMatrix) : 0),
    0
  );
  const pnlPct =
    totalCostBasisConverted !== 0
      ? unrealizedPnl / Math.abs(totalCostBasisConverted)
      : grossPositionVal !== 0
      ? unrealizedPnl / Math.abs(grossPositionVal)
      : 0;

  // Hero Row
  $("#metric-netliq").textContent = formatMoney(netLiq, ccy);

  const pnlEl = $("#metric-pnl");
  pnlEl.textContent = formatSignedMoney(unrealizedPnl, ccy);
  pnlEl.className = `hero-val font-mono ${pnlClass(unrealizedPnl)}`;

  const pnlPctEl = $("#metric-pnl-pct");
  pnlPctEl.textContent = formatPct(pnlPct, { signed: true });
  pnlPctEl.className = `hero-pct-badge ${pnlClass(unrealizedPnl)}`;

  // Key Metrics Grid
  $("#metric-positions").textContent = formatMoney(grossPositionVal, ccy);
  $("#metric-maint-margin").textContent = formatMoney(maintMargin, ccy);
  $("#metric-excess-liq").textContent = formatMoney(excessLiq, ccy);
}

// ---------------------------------------------------------------------------------------
// Section 3: Holdings (Reflects Section 1 Selection)
// ---------------------------------------------------------------------------------------

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

  const totalFilteredValue = rows.reduce(
    (acc, p) => acc + convertAmount(p.market_value ?? 0, p.currency, ccy, state.fxMatrix),
    0
  );
  $("#positions-count").textContent = `${rows.length} ${
    rows.length === 1 ? "position" : "positions"
  } · ${formatMoney(totalFilteredValue, ccy)}`;

  for (const th of document.querySelectorAll("#positions-table th[data-sort]")) {
    th.classList.toggle("sorted", th.dataset.sort === key);
    th.dataset.dir = th.dataset.sort === key ? (dir > 0 ? "asc" : "desc") : "";
  }

  const tbody = $("#positions-table tbody");
  tbody.innerHTML = rows.length
    ? rows
        .map((p) => {
          const expiry = p.last_trade_date
            ? esc(p.last_trade_date)
            : '<span class="muted">—</span>';
          const secType = p.sec_type || "STOCKS";
          const secClass = secType.toLowerCase().replace(/\s+/g, "-");
          const exchangeBadge = p.exchange
            ? `<span class="exchange-badge">${esc(p.exchange)}</span>`
            : '<span class="muted">—</span>';
          const symbolHtml = p.symbol
            ? `<span class="symbol-code">${esc(p.symbol)}</span>`
            : '<span class="muted">—</span>';
          const avgPriceHtml =
            p.avg_price != null ? formatMoney(p.avg_price, p.currency) : '<span class="muted">—</span>';
          const costBasisHtml =
            p.cost_basis != null
              ? formatMoney(convertAmount(p.cost_basis, p.currency, ccy, state.fxMatrix), ccy)
              : '<span class="muted">—</span>';
          const pnlHtml =
            p.cost_basis != null && p.unrealized_pnl != null
              ? `<div>${formatSignedMoney(convertAmount(p.unrealized_pnl, p.currency, ccy, state.fxMatrix), ccy)}</div>
                 <div class="small-pct">${formatPct(p.cost_basis !== 0 ? p.unrealized_pnl / Math.abs(p.cost_basis) : 0, { signed: true })}</div>`
              : '<span class="muted">—</span>';

          return `
          <tr>
            <td>
              <div class="instrument-name">${esc(p.instrument)}</div>
            </td>
            <td>${symbolHtml}</td>
            <td>
              <span class="sec-badge ${esc(secClass)}">${esc(secType)}</span>
            </td>
            <td>${exchangeBadge}</td>
            <td>${expiry}</td>
            <td class="num font-mono">${formatQty(p.position)}</td>
            <td class="num font-mono">${avgPriceHtml}</td>
            <td class="num font-mono">${formatMoney(p.mark_price, p.currency)}</td>
            <td class="num font-mono">${costBasisHtml}</td>
            <td class="num font-mono strong">${formatMoney(convertAmount(p.market_value, p.currency, ccy, state.fxMatrix), ccy)}</td>
            <td class="num"><span class="currency-badge">${esc(p.currency)}</span></td>
            <td class="num font-mono ${p.cost_basis != null ? pnlClass(p.unrealized_pnl) : ""}">
              ${pnlHtml}
            </td>
          </tr>`;
        })
        .join("")
    : `<tr><td colspan="12" class="empty muted">No positions match the current account or search filter.</td></tr>`;
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

  const totalCashConverted = allCashItems.reduce(
    (acc, c) => acc + convertAmount(c.amount, c.currency, ccy, state.fxMatrix),
    0
  );

  $("#cash-balances-caption").textContent = `${filteredSnaps.length} ${
    filteredSnaps.length === 1 ? "account" : "accounts"
  } · ${formatMoney(totalCashConverted, ccy)} total cash`;

  const tbody = $("#cash-table tbody");
  tbody.innerHTML = allCashItems.length
    ? allCashItems
        .map((c) => {
          const displayAcct =
            c.broker_name === "Futu" && c.account_id.length > 6
              ? `...${c.account_id.slice(-4)}`
              : c.account_id;
          return `
          <tr>
            <td>
              <span class="account-tag">${esc(displayAcct)}</span>
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
              ${formatMoney(convertAmount(c.amount, c.currency, ccy, state.fxMatrix), ccy)}
            </td>
          </tr>`;
        })
        .join("")
    : `<tr><td colspan="5" class="empty muted">No cash balances available.</td></tr>`;
}

// ---------------------------------------------------------------------------------------
// Event Wiring & Subpage Navigation
// ---------------------------------------------------------------------------------------

function switchPage(pageId) {
  state.activePage = pageId;

  // Update sidebar active states
  for (const btn of $$(".sidebar-item[data-page]")) {
    btn.classList.toggle("active", btn.dataset.page === pageId);
  }

  // Switch active subpage
  for (const subpage of $$(".subpage")) {
    const isMatch = subpage.id === `page-${pageId}`;
    subpage.hidden = !isMatch;
    subpage.classList.toggle("active", isMatch);
  }
}

function setupSidebarNavigation() {
  const items = $$(".sidebar-item[data-page]");
  for (const item of items) {
    item.addEventListener("click", () => {
      const pageId = item.dataset.page;
      window.location.hash = pageId;
      switchPage(pageId);
    });
  }

  // Support initial hash (e.g. #about, #settings)
  const initialHash = window.location.hash.replace("#", "").toLowerCase();
  if (initialHash && $(`#page-${initialHash}`)) {
    switchPage(initialHash);
  }
}

function wireEvents() {
  setupSidebarNavigation();

  // Head controls global data refresh
  $("#refresh-btn").addEventListener("click", load);

  // FX currency selection is purely an instantaneous GUI recalculation
  $("#currency-select").addEventListener("change", (e) => {
    state.currency = e.target.value;
    render();
  });

  // Search filter
  $("#search").addEventListener("input", (e) => {
    state.search = e.target.value;
    renderPositions();
  });

  // Column sorting
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

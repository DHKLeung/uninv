/**
 * uninv - Unified Investing Dashboard
 *
 * Consumes unified backend snapshot (/api/v1/snapshot) and live FX rates (/api/v1/fx).
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
  brokers: [],
  snapshots: [], // list of BrokerAccountSnapshot objects
  selectedAccount: "", // empty for "All", or account_id string
  search: "",
  currency: "USD",
  asof: null,
  sort: { key: "market_value", dir: -1 },
  fxRates: {}, // Map of "FROM->TO" to rate float
};

// ---------------------------------------------------------------------------------------
// Data Loading & FX Resolution
// ---------------------------------------------------------------------------------------

/**
 * Scan all snapshots to discover all non-target currencies present in positions,
 * cash balances, and account base values, then query /api/v1/fx for every required pair.
 */
async function fetchRequiredFxRates(targetCurrency) {
  const target = (targetCurrency || "USD").toUpperCase();
  const sourceCurrencies = new Set();

  for (const snap of state.snapshots) {
    if (snap.account_values?.currency) {
      sourceCurrencies.add(snap.account_values.currency.toUpperCase());
    }
    for (const cb of snap.account_values?.cash_balances ?? []) {
      if (cb.currency) {
        sourceCurrencies.add(cb.currency.toUpperCase());
      }
    }
    for (const p of snap.positions ?? []) {
      if (p.currency) {
        sourceCurrencies.add(p.currency.toUpperCase());
      }
    }
  }

  const pairsToFetch = [];
  for (const fromCcy of sourceCurrencies) {
    if (fromCcy !== target) {
      const pairKey = `${fromCcy}->${target}`;
      pairsToFetch.push({ from: fromCcy, to: target, key: pairKey });
    }
  }

  if (pairsToFetch.length === 0) {
    return;
  }

  await Promise.all(
    pairsToFetch.map(({ from, to, key }) =>
      apiGet(`/api/v1/fx?base=${encodeURIComponent(from)}&quote=${encodeURIComponent(to)}`)
        .then((fx) => {
          state.fxRates[key] = fx.rate;
          if (fx.rate > 0) {
            state.fxRates[`${to}->${from}`] = 1.0 / fx.rate;
          }
        })
        .catch((e) => {
          console.warn(`Could not refresh live FX rate for ${key}:`, e);
        })
    )
  );
}

async function load() {
  const btn = $("#refresh-btn");
  btn.disabled = true;
  btn.textContent = "Loading…";

  try {
    // 0. Sync available currencies from backend
    apiGet("/api/v1/currencies")
      .then((ccys) => {
        const select = $("#currency-select");
        if (!select || !Array.isArray(ccys)) return;
        const existing = new Set(Array.from(select.options).map((o) => o.value));
        for (const c of ccys) {
          if (!existing.has(c)) {
            const opt = document.createElement("option");
            opt.value = c;
            const sym = CURRENCY_SYMBOLS[c] ? ` (${CURRENCY_SYMBOLS[c].trim()})` : "";
            opt.textContent = `${c}${sym}`;
            select.appendChild(opt);
          }
        }
      })
      .catch(() => {});

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

    const snapshots = await Promise.all(snapshotPromises);
    state.snapshots = snapshots;

    // 4. Dynamically detect ALL currencies across accounts, positions, and cash,
    //    then ping /api/v1/fx for every conversion needed into the target currency.
    await fetchRequiredFxRates(state.currency);

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

/**
 * Section 1: Accounts (Horizontal tiles)
 */
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
        state.fxRates
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
    const acctNetLiq = convertAmount(av?.net_liquidation ?? 0, av?.currency, ccy, state.fxRates);
    const posCount = s.positions?.length ?? 0;

    html += `
      <div class="account-tile ${isActive ? "active" : ""}" data-account="${esc(s.account_id)}">
        <div class="account-tile-header">
          <span class="account-tile-name">${esc(s.account_id)}</span>
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
      const acctId = tile.dataset.account;
      // Selecting the same account toggles back to All
      if (state.selectedAccount === acctId && acctId !== "") {
        state.selectedAccount = "";
      } else {
        state.selectedAccount = acctId;
      }
      renderAccounts();
      renderMetrics();
      renderPositions();
      renderCashBalances();
    });
  }
}

/**
 * Section 2: Metrics Board (One big cohesive section, not tiles)
 */
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
    $("#metrics-scope-label").textContent = `ACCOUNT: ${state.selectedAccount}`;
    $("#metrics-scope-desc").textContent = `${brokerName} account-level margin & balances`;
  }
  $("#metrics-currency-name").textContent = ccy;

  // Aggregate values
  const netLiq = filteredSnaps.reduce(
    (acc, s) =>
      acc +
      convertAmount(
        s.account_values?.net_liquidation ?? 0,
        s.account_values?.currency,
        ccy,
        state.fxRates
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
        state.fxRates
      ),
    0
  );

  const equityWithLoan = filteredSnaps.reduce(
    (acc, s) =>
      acc +
      convertAmount(
        s.account_values?.equity_with_loan_value ?? 0,
        s.account_values?.currency,
        ccy,
        state.fxRates
      ),
    0
  );

  const cashBalance = filteredSnaps.reduce(
    (acc, s) =>
      acc +
      convertAmount(
        s.account_values?.cash_balance ?? 0,
        s.account_values?.currency,
        ccy,
        state.fxRates
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
        state.fxRates
      ),
    0
  );

  const availableFunds = filteredSnaps.reduce(
    (acc, s) =>
      acc +
      convertAmount(
        s.account_values?.available_funds ?? 0,
        s.account_values?.currency,
        ccy,
        state.fxRates
      ),
    0
  );

  const buyingPower = filteredSnaps.reduce(
    (acc, s) =>
      acc +
      convertAmount(
        s.account_values?.buying_power ?? 0,
        s.account_values?.currency,
        ccy,
        state.fxRates
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
        state.fxRates
      ),
    0
  );

  const initMargin = filteredSnaps.reduce(
    (acc, s) =>
      acc +
      convertAmount(
        s.account_values?.init_margin_req ?? 0,
        s.account_values?.currency,
        ccy,
        state.fxRates
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
        state.fxRates
      ),
    0
  );

  // Compute Unrealized PnL %
  const totalPositions = getAllFilteredPositions();
  const totalCostBasisConverted = totalPositions.reduce(
    (acc, p) => acc + convertAmount(p.cost_basis ?? 0, p.currency, ccy, state.fxRates),
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

  $("#metric-equity").textContent = formatMoney(equityWithLoan, ccy);

  // Key Metrics Grid
  const cashEl = $("#metric-cash");
  cashEl.textContent = formatMoney(cashBalance, ccy);
  cashEl.className = `cell-value font-mono ${pnlClass(cashBalance)}`;

  $("#metric-positions").textContent = formatMoney(grossPositionVal, ccy);
  $("#metric-avail").textContent = formatMoney(availableFunds, ccy);
  $("#metric-buyingpower").textContent = formatMoney(buyingPower, ccy);
  $("#metric-excess-liq").textContent = formatMoney(excessLiq, ccy);
  $("#metric-init-margin").textContent = formatMoney(initMargin, ccy);
  $("#metric-maint-margin").textContent = formatMoney(maintMargin, ccy);
}

/**
 * Section 3: Holdings - Positions Table
 */
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
    (acc, p) => acc + convertAmount(p.market_value ?? 0, p.currency, ccy, state.fxRates),
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
          const pnlPct =
            p.cost_basis !== 0 ? (p.unrealized_pnl ?? 0) / Math.abs(p.cost_basis) : 0;

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
            <td class="num font-mono">${formatMoney(p.avg_price, p.currency)}</td>
            <td class="num font-mono">${formatMoney(p.mark_price, p.currency)}</td>
            <td class="num font-mono">${formatMoney(convertAmount(p.cost_basis, p.currency, ccy, state.fxRates), ccy)}</td>
            <td class="num font-mono strong">${formatMoney(convertAmount(p.market_value, p.currency, ccy, state.fxRates), ccy)}</td>
            <td class="num"><span class="currency-badge">${esc(p.currency)}</span></td>
            <td class="num font-mono ${pnlClass(p.unrealized_pnl)}">
              ${
                p.unrealized_pnl != null
                  ? `<div>${formatSignedMoney(convertAmount(p.unrealized_pnl, p.currency, ccy, state.fxRates), ccy)}</div>
                     <div class="small-pct">${formatPct(pnlPct, { signed: true })}</div>`
                  : '<span class="muted">—</span>'
              }
            </td>
          </tr>`;
        })
        .join("")
    : `<tr><td colspan="12" class="empty muted">No positions match the current account or search filter.</td></tr>`;
}

/**
 * Section 3: Holdings - Cash Balances Table
 */
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

  const totalCashConverted = filteredSnaps.reduce(
    (acc, s) =>
      acc +
      convertAmount(
        s.account_values?.cash_balance ?? 0.0,
        s.account_values?.currency,
        ccy,
        state.fxRates
      ),
    0
  );

  $("#cash-balances-caption").textContent = `${filteredSnaps.length} ${
    filteredSnaps.length === 1 ? "account" : "accounts"
  } · ${formatMoney(totalCashConverted, ccy)} total cash`;

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
              ${formatMoney(convertAmount(c.amount, c.currency, ccy, state.fxRates), ccy)}
            </td>
          </tr>`;
        })
        .join("")
    : `<tr><td colspan="5" class="empty muted">No cash balances available.</td></tr>`;
}

// ---------------------------------------------------------------------------------------
// Event Wiring & Subpage Navigation
// ---------------------------------------------------------------------------------------

function setupSidebarNavigation() {
  const items = $$(".sidebar-item[data-page]");
  for (const item of items) {
    item.addEventListener("click", () => {
      const pageId = item.dataset.page;
      state.activePage = pageId;

      // Update sidebar active states
      for (const btn of items) {
        btn.classList.toggle("active", btn === item);
      }

      // Switch active subpage
      for (const subpage of $$(".subpage")) {
        const isMatch = subpage.id === `page-${pageId}`;
        subpage.hidden = !isMatch;
        subpage.classList.toggle("active", isMatch);
      }
    });
  }
}

function wireEvents() {
  setupSidebarNavigation();

  $("#refresh-btn").addEventListener("click", load);

  $("#currency-select").addEventListener("change", async (e) => {
    state.currency = e.target.value;
    await fetchRequiredFxRates(state.currency);
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

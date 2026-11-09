/**
 * uninv - Unified Investing Dashboard
 *
 * Global Data Pulling:
 * All broker accounts, unified snapshots, and the complete FX matrix (/api/v1/fx)
 * are fetched globally on app load or when clicking Refresh.
 * Data is fixed in memory; currency switching is an instantaneous GUI calculation
 * using the pre-pulled FX matrix without making any additional network requests.
 *
 * Unidirectional Portfolio Interaction:
 * In the Portfolio page, Section 1 (Accounts horizontal tiles) is the sole selector.
 * Selecting an account triggers a single unidirectional reaction path:
 * Section 1 Tiles -> Section 2 Account Values Board -> Section 3 Positions & Cash Balances.
 */

import { apiGet, apiPost, backendUrl } from "./api.js";
import {
  CURRENCY_SYMBOLS,
  calculateDaysLeft,
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
  finishTime: null, // UTC timestamp when all fetches completed
  endpointTimestamps: [], // [{ label: "FX Matrix (/api/v1/fx)", asof: "..." }]

  // Display / Interaction State
  selectedAccount: "", // empty for "All", or account_id string
  currency: "USD",
  search: "",
  sort: { key: "market_value", dir: -1 },

  // Auto-refresh State
  refreshInterval: "manual", // "manual", "1", "2", "5", "10"
  isLoading: false,

  // Settings State
  settings: {
    isEditing: false,
    brokerGateways: {
      ibkr: { host: "127.0.0.1", port: 7496 },
      futu: { host: "127.0.0.1", port: 11111 },
    },
    enabledBrokers: { ibkr: true, futu: true },
    connectionStatus: {}, // { ibkr: { connected: true, message: "..." } }
  },
};

// ---------------------------------------------------------------------------------------
// Helper Utilities
// ---------------------------------------------------------------------------------------

// Clear legacy stored enabled brokers if any existed
try {
  localStorage.removeItem("uninv_enabled_brokers");
} catch (_) {}

function formatUtcTimestamp(isoStr) {
  if (!isoStr) return "—";
  const dt = new Date(isoStr);
  if (Number.isNaN(dt.getTime())) return isoStr;
  const y = dt.getUTCFullYear();
  const m = String(dt.getUTCMonth() + 1).padStart(2, "0");
  const d = String(dt.getUTCDate()).padStart(2, "0");
  const hh = String(dt.getUTCHours()).padStart(2, "0");
  const mm = String(dt.getUTCMinutes()).padStart(2, "0");
  const ss = String(dt.getUTCSeconds()).padStart(2, "0");
  return `${y}-${m}-${d} ${hh}:${mm}:${ss} +00:00`;
}

function formatAccountDisplay(brokerId, accountId) {
  if (brokerId === "futu" && accountId && accountId.length > 6) {
    return `...${accountId.slice(-4)}`;
  }
  return accountId || "–";
}

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

let autoRefreshTimer = null;

const INTERVAL_LABELS = {
  "30": "30 secs",
  "60": "1 min",
  "120": "2 mins",
  "300": "5 mins",
  "600": "10 mins",
};

/**
 * Update the refresh button appearance, disabled state, and tooltip title.
 * Only clickable when refreshInterval is "manual".
 */
function updateRefreshButton() {
  const btn = $("#refresh-btn");
  if (!btn) return;
  const isManual = state.refreshInterval === "manual";
  if (state.isLoading) {
    btn.disabled = true;
    btn.classList.add("loading");
    btn.title = "Refreshing portfolio…";
  } else {
    btn.classList.remove("loading");
    btn.disabled = !isManual;
    const intervalLabel = INTERVAL_LABELS[state.refreshInterval] || `${state.refreshInterval}s`;
    btn.title = isManual
      ? "Refresh portfolio"
      : `Auto-refresh active (${intervalLabel}) - select Manual to refresh manually`;
  }
}

/**
 * Configure and schedule recurring auto-refresh timer.
 * Skips overlaps if a previous refresh is still active when interval triggers.
 */
function scheduleAutoRefresh() {
  if (autoRefreshTimer) {
    clearInterval(autoRefreshTimer);
    autoRefreshTimer = null;
  }

  const intervalSec =
    state.refreshInterval === "manual" ? 0 : parseInt(state.refreshInterval, 10);
  if (intervalSec > 0) {
    const ms = intervalSec * 1000;
    autoRefreshTimer = setInterval(() => {
      if (state.isLoading) {
        console.log("Auto-refresh skipped: previous refresh still in progress");
        return;
      }
      load();
    }, ms);
  }
  updateRefreshButton();
}

/**
 * Global data refresh: pulls all broker data, account snapshots, and the full FX matrix.
 * Records finish timestamp as the authoritative 'As of' time.
 * Skips execution if a refresh is already in progress.
 */
async function load() {
  if (state.isLoading) {
    console.log("Refresh call skipped: previous refresh still in progress");
    return;
  }
  state.isLoading = true;
  updateRefreshButton();

  const endpointTimestamps = [];

  try {
    // 1. Fetch brokers, FX matrix, and gateway configuration concurrently
    const [brokers, fxData, gatewayData] = await Promise.all([
      apiGet("/api/v1/supporting-brokers"),
      apiGet("/api/v1/fx"),
      apiGet("/api/v1/broker-gateway-config").catch(() => ({ gateways: {} })),
    ]);

    state.brokers = brokers;
    state.currencies = fxData.currencies || [];
    state.fxMatrix = fxData.rates || {};

    if (gatewayData?.gateways) {
      state.settings.brokerGateways = {
        ...state.settings.brokerGateways,
        ...gatewayData.gateways,
      };
    }

    if (fxData.asof) {
      endpointTimestamps.push({
        label: "FX Matrix",
        asof: fxData.asof,
      });
    }

    syncCurrencyDropdown(state.currencies);

    // Default all brokers to enabled on fresh startup (in-memory only, no previous state memory)
    for (const b of brokers) {
      if (state.settings.enabledBrokers[b.id] === undefined) {
        state.settings.enabledBrokers[b.id] = true;
      }
    }
    const activeBrokers = brokers.filter((b) => state.settings.enabledBrokers[b.id] !== false);

    // Test gateway connection for all brokers in background regardless of checkbox state
    testBrokerConnections().catch(() => {});

    const brokerMap = Object.fromEntries(brokers.map((b) => [b.id, b.name]));

    // 2. Fetch accounts for each active broker
    const accountResponses = await Promise.all(
      activeBrokers.map(async (b) => {
        try {
          const resp = await apiGet(`/api/v1/accounts?broker_id=${encodeURIComponent(b.id)}`);
          if (resp.asof) {
            endpointTimestamps.push({
              label: `${brokerMap[b.id] || b.id} Accounts`,
              asof: resp.asof,
            });
          }
          return resp;
        } catch (err) {
          console.warn(`Failed to fetch accounts for ${b.id}:`, err);
          return { broker_id: b.id, accounts: [], asof: null };
        }
      })
    );

    // 3. Fetch snapshots for all discovered accounts
    const snapshotPromises = [];
    for (const resp of accountResponses) {
      for (const acctId of resp.accounts) {
        snapshotPromises.push(
          apiGet(
            `/api/v1/snapshot?broker_id=${encodeURIComponent(resp.broker_id)}&account_id=${encodeURIComponent(acctId)}`
          )
            .then((snap) => {
              if (snap.asof) {
                const acctFmt = formatAccountDisplay(snap.broker_id, snap.account_id);
                endpointTimestamps.push({
                  label: `${brokerMap[snap.broker_id] || snap.broker_id} (${acctFmt})`,
                  asof: snap.asof,
                });
              }
              return {
                ...snap,
                broker_name: brokerMap[snap.broker_id] ?? snap.broker_id,
              };
            })
            .catch((err) => {
              console.warn(`Failed to fetch snapshot for ${resp.broker_id}:${acctId}:`, err);
              return null;
            })
        );
      }
    }

    const rawSnapshots = await Promise.all(snapshotPromises);
    state.snapshots = rawSnapshots.filter(Boolean);

    // 4. Record the finishing timestamp of all network operations
    state.finishTime = new Date().toISOString();
    state.endpointTimestamps = endpointTimestamps;

    setBackendStatus(true);
    hideError();
    render();

    // If Settings page is currently active, render settings
    if (state.activePage === "settings") {
      renderSettings();
    }
    // Background probe connection statuses so settings is immediately warm
    testBrokerConnections().then(() => {
      if (state.activePage === "settings") renderSettings();
    });
  } catch (err) {
    setBackendStatus(false);
    showError(String(err?.message ?? err));
  } finally {
    state.isLoading = false;
    updateRefreshButton();
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
  if (el) {
    el.textContent = message;
    el.hidden = false;
  }
}

function hideError() {
  const el = $("#error-banner");
  if (el) el.hidden = true;
}

// ---------------------------------------------------------------------------------------
// Rendering Pipeline
// ---------------------------------------------------------------------------------------

function render() {
  renderHeader();
  renderAccounts();
  renderAccountValues();
  renderPositions();
  renderCashBalances();
}

function renderHeader() {
  // Main "As of" shows the exact finish time of all queries
  if (state.finishTime) {
    $("#as-of").textContent = `As of ${formatUtcTimestamp(state.finishTime)}`;
  } else {
    $("#as-of").textContent = "";
  }

  // Populate Tooltip with each endpoint's respective asof timestamp
  const tooltipList = $("#as-of-tooltip-list");
  if (tooltipList) {
    if (state.endpointTimestamps.length > 0) {
      tooltipList.innerHTML = state.endpointTimestamps
        .map(
          (item) => `
          <div class="tooltip-item">
            <span class="tooltip-item-label">${esc(item.label)}</span>
            <span class="tooltip-item-time font-mono">${esc(formatUtcTimestamp(item.asof))}</span>
          </div>`
        )
        .join("");
    } else {
      tooltipList.innerHTML = `<div class="tooltip-empty">No data timestamps recorded</div>`;
    }
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
// Section 1: Accounts Horizontal Tiles (Sole Selector)
// ---------------------------------------------------------------------------------------

function updateAccountTilesActiveState() {
  const listEl = $("#accounts-horizontal-list");
  if (!listEl) return;
  for (const tile of listEl.querySelectorAll(".account-tile")) {
    const acct = tile.dataset.account;
    tile.classList.toggle("active", acct === state.selectedAccount);
  }
}

function onSelectAccount(acctId) {
  if (state.selectedAccount === acctId && acctId !== "") {
    state.selectedAccount = "";
  } else {
    state.selectedAccount = acctId;
  }

  updateAccountTilesActiveState();
  renderAccountValues();
  renderPositions();
  renderCashBalances();
}

function renderAccounts() {
  const ccy = state.currency;
  const listEl = $("#accounts-horizontal-list");
  if (!listEl) return;

  const totalAccounts = state.snapshots.length;
  const totalPositionsCount = state.snapshots.reduce(
    (acc, s) => acc + (s.positions?.length ?? 0),
    0
  );

  $("#accounts-caption").textContent = `${totalAccounts} accounts · ${state.brokers.length} broker(s)`;

  // Tile 1: "All Accounts" (Sum of NLV across all accounts with FX conversion)
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
        <span class="account-tile-caption">${totalAccounts} accounts · ${totalPositionsCount} ${
          totalPositionsCount === 1 ? "position" : "positions"
        }</span>
      </div>
    </div>
  `;

  // Tile 2+: Individual Broker Accounts
  for (const s of state.snapshots) {
    const isActive = state.selectedAccount === s.account_id;
    const av = s.account_values;
    const acctNetLiq = convertAmount(av?.net_liquidation ?? 0, av?.currency, ccy, state.fxMatrix);
    const posCount = s.positions?.length ?? 0;
    const displayName = formatAccountDisplay(s.broker_id, s.account_id);

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
// Section 2: Account Values (Reflects Section 1 Selection)
// ---------------------------------------------------------------------------------------

function renderAccountValues() {
  const ccy = state.currency;
  const filteredSnaps = getFilteredSnapshots();

  // Header Subtitle / Scope Label
  if (state.selectedAccount === "") {
    $("#metrics-scope-label").textContent = "All Accounts Consolidated";
  } else {
    const snap = state.snapshots.find((s) => s.account_id === state.selectedAccount);
    const brokerName = snap?.broker_name || "Broker";
    const displayId = formatAccountDisplay(snap?.broker_id, state.selectedAccount);
    $("#metrics-scope-label").textContent = `${displayId} · ${brokerName}`;
  }

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

  // Cash Balance: sum of actual cash balances converted to selected currency
  const cashBalance = filteredSnaps.reduce(
    (acc, s) =>
      acc +
      (s.account_values?.cash_balances ?? []).reduce(
        (subAcc, cb) => subAcc + convertAmount(cb.amount, cb.currency, ccy, state.fxMatrix),
        0
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

  // Row 1: Net Liquidation Value, Gross Position Value, Cash Balance
  $("#metric-netliq").textContent = formatMoney(netLiq, ccy);
  $("#metric-positions").textContent = formatMoney(grossPositionVal, ccy);
  $("#metric-cash-balance").textContent = formatMoney(cashBalance, ccy);

  // Row 2: Unrealised P&L, Maintenance Margin, Excess Liquidity
  const pnlEl = $("#metric-pnl");
  pnlEl.textContent = formatSignedMoney(unrealizedPnl, ccy);
  pnlEl.className = `val-number font-mono ${pnlClass(unrealizedPnl)}`;

  const pnlPctEl = $("#metric-pnl-pct");
  pnlPctEl.textContent = formatPct(pnlPct, { signed: true });
  pnlPctEl.className = `hero-pct-badge ${pnlClass(unrealizedPnl)}`;

  // For Maintenance Margin & Excess Liquidity:
  // When All Accounts is selected, display "—" as summing across brokers is not applicable.
  if (state.selectedAccount === "") {
    $("#metric-maint-margin").innerHTML = '<span class="muted">—</span>';
    $("#metric-excess-liq").innerHTML = '<span class="muted">—</span>';
  } else {
    const singleSnap = filteredSnaps[0];
    const av = singleSnap?.account_values;
    const maintMargin = av?.maint_margin_req != null
      ? convertAmount(av.maint_margin_req, av.currency, ccy, state.fxMatrix)
      : 0;
    const excessLiq = av?.excess_liquidity != null
      ? convertAmount(av.excess_liquidity, av.currency, ccy, state.fxMatrix)
      : 0;

    $("#metric-maint-margin").textContent = formatMoney(maintMargin, ccy);
    $("#metric-excess-liq").textContent = formatMoney(excessLiq, ccy);
  }
}

// ---------------------------------------------------------------------------------------
// Section 3: Holdings (Reflects Section 1 Selection)
// ---------------------------------------------------------------------------------------

function renderPositions() {
  const ccy = state.currency;
  const q = state.search.trim().toLowerCase();

  // Positions are never aggregated even if accounts trade the same symbol
  let rows = getAllFilteredPositions().filter((p) => {
    if (!q) return true;
    return (
      (p.symbol && p.symbol.toLowerCase().includes(q)) ||
      (p.instrument && p.instrument.toLowerCase().includes(q)) ||
      (p.sec_type && p.sec_type.toLowerCase().includes(q)) ||
      (p.exchange && p.exchange.toLowerCase().includes(q)) ||
      (p.broker_name && p.broker_name.toLowerCase().includes(q)) ||
      (p.account_id && p.account_id.toLowerCase().includes(q))
    );
  });

  // Calculate scope total net liquidation for portfolio weight calculation (per selected account or all accounts)
  const filteredSnaps = getFilteredSnapshots();
  const scopeNetLiq = filteredSnaps.reduce(
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

  // Pre-calculate converted market value, weight, and days left per current account scope
  for (const p of rows) {
    p.marketValConverted = convertAmount(p.market_value, p.currency, ccy, state.fxMatrix);
    p.weight = scopeNetLiq > 0 ? (p.marketValConverted / scopeNetLiq) : 0;
    if (p.days_left == null && p.last_trading_date) {
      p.days_left = calculateDaysLeft(p.last_trading_date);
    }
  }

  const { key, dir } = state.sort;
  rows = rows.toSorted((a, b) => {
    let x = a[key];
    let y = b[key];
    const xNull = x === null || x === undefined || x === "";
    const yNull = y === null || y === undefined || y === "";
    if (xNull && yNull) return 0;
    if (xNull) return 1;
    if (yNull) return -1;
    if (typeof x === "number" && typeof y === "number") {
      return (x - y) * dir;
    }
    return String(x).localeCompare(String(y)) * dir;
  });

  for (const th of document.querySelectorAll("#positions-table th[data-sort]")) {
    th.classList.toggle("sorted", th.dataset.sort === key);
    th.dataset.dir = th.dataset.sort === key ? (dir > 0 ? "asc" : "desc") : "";
  }

  const tbody = $("#positions-table tbody");
  tbody.innerHTML = rows.length
    ? rows
        .map((p) => {
          const displayAcct = formatAccountDisplay(p.broker_id, p.account_id);
          const brokerAccountHtml = `
            <div class="cell-stacked">
              <span class="cell-main text-broker">${esc(p.broker_name)}</span>
              <span class="cell-sub text-account font-mono">${esc(displayAcct)}</span>
            </div>
          `;

          const symbolHtml = p.symbol
            ? `<span class="symbol-code">${esc(p.symbol)}</span>`
            : '<span class="muted">—</span>';

          const instrumentSymbolHtml = `
            <div class="cell-stacked">
              <span class="cell-main instrument-name">${esc(p.instrument)}</span>
              <span class="cell-sub">${symbolHtml}</span>
            </div>
          `;

          const secType = p.sec_type || "STOCKS";
          const secClass = secType.toLowerCase().replace(/\s+/g, "-");
          const secBadge = `<span class="sec-badge ${esc(secClass)}">${esc(secType)}</span>`;
          const exchangeBadge = p.exchange
            ? `<span class="exchange-badge">${esc(p.exchange)}</span>`
            : '<span class="muted">—</span>';

          // Type / Exchange column (Upper: Type, Lower: Exchange)
          const typeExchangeHtml = `
            <div class="cell-stacked">
              <span class="cell-main">${secBadge}</span>
              <span class="cell-sub">${exchangeBadge}</span>
            </div>
          `;

          const avgPriceHtml =
            p.avg_price != null ? formatMoney(p.avg_price, p.currency) : '<span class="muted">—</span>';
          const markPriceHtml = formatMoney(p.mark_price, p.currency);

          const costBasisConverted =
            p.cost_basis != null
              ? convertAmount(p.cost_basis, p.currency, ccy, state.fxMatrix)
              : null;
          const costBasisHtml =
            costBasisConverted != null ? formatMoney(costBasisConverted, ccy) : '<span class="muted">—</span>';

          const marketValConverted = p.marketValConverted;
          const pnlConverted = convertAmount(p.unrealized_pnl, p.currency, ccy, state.fxMatrix);

          const lastTradeDateHtml = p.last_trading_date
            ? esc(p.last_trading_date)
            : '<span class="muted">—</span>';

          const daysLeftVal =
            p.days_left != null ? p.days_left : calculateDaysLeft(p.last_trading_date);
          const daysLeftHtml =
            daysLeftVal != null
              ? esc(daysLeftVal)
              : '<span class="muted">—</span>';

          const pnlHtml =
            p.cost_basis != null
              ? `<div>${formatSignedMoney(pnlConverted, ccy)}</div>
                 <div class="small-pct">${formatPct(p.cost_basis !== 0 ? p.unrealized_pnl / Math.abs(p.cost_basis) : 0, { signed: true })}</div>`
              : '<span class="muted">—</span>';

          // Portfolio weight % calculated per currently selected account
          let weightHtml = '<span class="muted">—</span>';
          if (scopeNetLiq > 0) {
            weightHtml = `<span class="font-mono">${formatPct(p.weight, { signed: false, digits: 2 })}</span>`;
          }

          return `
          <tr>
            <td>${brokerAccountHtml}</td>
            <td>${instrumentSymbolHtml}</td>
            <td>${typeExchangeHtml}</td>
            <td class="num font-mono">${formatQty(p.position)}</td>
            <td class="num font-mono">${avgPriceHtml}</td>
            <td class="num font-mono">${markPriceHtml}</td>
            <td class="num font-mono">${costBasisHtml}</td>
            <td class="num font-mono strong">${formatMoney(marketValConverted, ccy)}</td>
            <td class="font-mono">${lastTradeDateHtml}</td>
            <td class="num font-mono">${daysLeftHtml}</td>
            <td class="num font-mono ${p.cost_basis != null ? pnlClass(p.unrealized_pnl) : ""}">
              ${pnlHtml}
            </td>
            <td class="num">${weightHtml}</td>
            <td class="num"><span class="currency-badge">${esc(p.currency)}</span></td>
          </tr>`;
        })
        .join("")
    : `<tr><td colspan="13" class="empty muted">No positions match the current account or search filter.</td></tr>`;
}

function renderCashBalances() {
  const ccy = state.currency;
  const filteredSnaps = getFilteredSnapshots();

  // Cash balances are not aggregated; each account's cash balance items are displayed separately
  const allCashItems = filteredSnaps.flatMap((s) =>
    (s.account_values?.cash_balances ?? []).map((cb) => ({
      broker_id: s.broker_id,
      account_id: s.account_id,
      broker_name: s.broker_name,
      currency: cb.currency,
      amount: cb.amount,
    }))
  );

  const tbody = $("#cash-table tbody");
  tbody.innerHTML = allCashItems.length
    ? allCashItems
        .map((c) => {
          const displayAcct = formatAccountDisplay(c.broker_id, c.account_id);
          const brokerAccountHtml = `
            <div class="cell-stacked">
              <span class="cell-main text-broker">${esc(c.broker_name)}</span>
              <span class="cell-sub text-account font-mono">${esc(displayAcct)}</span>
            </div>
          `;

          const rawAmountHtml = formatMoney(c.amount, c.currency);
          const convertedAmount = convertAmount(c.amount, c.currency, ccy, state.fxMatrix);
          const convertedAmountHtml = formatMoney(convertedAmount, ccy);

          return `
          <tr>
            <td>${brokerAccountHtml}</td>
            <td class="num">
              <span class="currency-badge">${esc(c.currency)}</span>
            </td>
            <td class="num font-mono strong ${pnlClass(c.amount)}">
              ${rawAmountHtml}
            </td>
            <td class="num font-mono strong ${pnlClass(c.amount)}">
              ${convertedAmountHtml}
            </td>
          </tr>`;
        })
        .join("")
    : `<tr><td colspan="4" class="empty muted">No cash balances available.</td></tr>`;
}

// ---------------------------------------------------------------------------------------
// Subpage Navigation & Settings Handlers
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

  if (pageId === "settings") {
    renderSettings();
    testBrokerConnections().then(() => {
      if (state.activePage === "settings") renderSettings();
    });
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

  const initialHash = window.location.hash.replace("#", "").toLowerCase();
  if (initialHash && $(`#page-${initialHash}`)) {
    switchPage(initialHash);
  }
}

// ---------------------------------------------------------------------------------------
// Settings Page Logic
// ---------------------------------------------------------------------------------------

async function renderSettings() {
  const listEl = $("#settings-brokers-list");
  if (!listEl) return;

  const isEditing = state.settings.isEditing;
  const editBtn = $("#settings-edit-btn");
  const saveBtn = $("#settings-save-btn");

  if (editBtn) editBtn.disabled = isEditing;
  if (saveBtn) saveBtn.disabled = !isEditing;

  const enabledBrokers = state.settings.enabledBrokers;
  const gateways = state.settings.brokerGateways;

  let html = "";
  for (const b of state.brokers) {
    const isChecked = enabledBrokers[b.id] !== false;
    const gw = gateways[b.id] || {
      host: "127.0.0.1",
      port: b.id === "ibkr" ? 7496 : 11111,
    };
    const conn = state.settings.connectionStatus[b.id];

    let statusBadge = "";
    if (conn) {
      if (conn.connected) {
        statusBadge = `<span class="conn-status ok" title="${esc(conn.message)}">✓ Connected</span>`;
      } else {
        statusBadge = `<span class="conn-status bad" title="${esc(conn.message)}">✗ Offline</span>`;
      }
    } else {
      statusBadge = `<span class="conn-status muted">Untested</span>`;
    }

    html += `
      <div class="settings-broker-row" data-broker="${esc(b.id)}">
        <label class="settings-checkbox-wrap">
          <input type="checkbox" class="broker-enable-toggle" data-broker="${esc(b.id)}" ${
            isChecked ? "checked" : ""
          } ${isEditing ? "" : "disabled"} />
          <span class="settings-broker-name">${esc(b.name)}</span>
        </label>

        <div class="settings-gateway-fields">
          <div class="settings-field-group">
            <label class="field-label" for="host-${esc(b.id)}">Host / IP:</label>
            <input type="text" id="host-${esc(b.id)}" class="host-input font-mono" data-broker="${esc(b.id)}" value="${esc(gw.host || "127.0.0.1")}" ${
              isEditing ? "" : "disabled"
            } placeholder="127.0.0.1" />
          </div>

          <div class="settings-field-group">
            <label class="field-label" for="port-${esc(b.id)}">Port:</label>
            <input type="number" id="port-${esc(b.id)}" class="port-input font-mono" data-broker="${esc(b.id)}" value="${gw.port}" ${
              isEditing ? "" : "disabled"
            } min="1" max="65535" />
          </div>
        </div>

        <div class="settings-conn-col">
          ${statusBadge}
        </div>
      </div>
    `;
  }

  listEl.innerHTML = html;
}

async function testBrokerConnections() {
  for (const b of state.brokers) {
    try {
      const res = await apiGet(`/api/v1/broker-connection-test?broker_id=${encodeURIComponent(b.id)}`);
      state.settings.connectionStatus[b.id] = {
        connected: res.connected,
        message: res.message,
      };
    } catch (e) {
      state.settings.connectionStatus[b.id] = {
        connected: false,
        message: String(e?.message ?? e),
      };
    }
  }
}

function wireSettingsEvents() {
  const editBtn = $("#settings-edit-btn");
  const saveBtn = $("#settings-save-btn");

  if (editBtn) {
    editBtn.addEventListener("click", () => {
      state.settings.isEditing = true;
      renderSettings();
    });
  }

  if (saveBtn) {
    saveBtn.addEventListener("click", async () => {
      saveBtn.disabled = true;
      saveBtn.textContent = "Saving…";

      // 1. Gather enabled checkboxes for current session (in-memory only, no memory across restarts)
      const toggles = $$(".broker-enable-toggle");
      const enabledMap = {};
      for (const t of toggles) {
        enabledMap[t.dataset.broker] = t.checked;
      }
      state.settings.enabledBrokers = enabledMap;

      // 2. Gather host and port for each broker
      for (const b of state.brokers) {
        const hostInp = $(`#host-${b.id}`);
        const portInp = $(`#port-${b.id}`);
        const hostVal = hostInp && hostInp.value.trim() ? hostInp.value.trim() : "127.0.0.1";
        const portVal = portInp ? Number.parseInt(portInp.value, 10) : (b.id === "ibkr" ? 7496 : 11111);

        state.settings.brokerGateways[b.id] = { host: hostVal, port: portVal };
        try {
          await apiPost("/api/v1/broker-gateway-config", {
            broker_id: b.id,
            host: hostVal,
            port: portVal,
          });
        } catch (e) {
          console.warn(`Failed to update gateway config for ${b.id}:`, e);
        }
      }

      // 3. Test connections
      await testBrokerConnections();

      // 4. Exit edit mode
      state.settings.isEditing = false;
      renderSettings();
      saveBtn.textContent = "Save";

      // 5. Reload portfolio data with updated settings
      load();
    });
  }
}

// ---------------------------------------------------------------------------------------
// Initialization & Global Event Wiring
// ---------------------------------------------------------------------------------------

function wireEvents() {
  setupSidebarNavigation();
  wireSettingsEvents();

  // Head controls global data refresh (only clickable when in manual mode)
  $("#refresh-btn").addEventListener("click", () => {
    if (state.refreshInterval === "manual" && !state.isLoading) {
      load();
    }
  });

  // Auto-refresh interval selection
  $("#refresh-interval-select").addEventListener("change", (e) => {
    state.refreshInterval = e.target.value;
    scheduleAutoRefresh();
  });

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

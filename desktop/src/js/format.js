/**
 * Number and currency formatting helpers with dynamic FX rate support.
 */

export const FX_RATES = {
  USD: 1.0,
  HKD: 7.8413,
  EUR: 0.8913,
  GBP: 0.7435,
  JPY: 154.20,
  CAD: 1.39,
  AUD: 1.53,
  CHF: 0.88,
  CNH: 7.23,
  SGD: 1.33,
  NZD: 1.68,
};

export const CURRENCY_SYMBOLS = {
  USD: "$",
  HKD: "HK$",
  EUR: "€",
  GBP: "£",
  JPY: "¥",
  CAD: "CA$",
  AUD: "A$",
  CHF: "CHF ",
  CNH: "CN¥",
  SGD: "S$",
  NZD: "NZ$",
};

/**
 * Update dynamic FX rate against USD base.
 */
export function setFxRate(currency, rate) {
  if (currency && typeof rate === "number" && rate > 0) {
    FX_RATES[currency] = rate;
  }
}

/**
 * Convert an amount from fromCurrency to toCurrency using the FX matrix or fallbacks.
 * fxMatrix is the nested map: fxMatrix[from][to] = rate.
 */
export function convertAmount(amount, fromCurrency, toCurrency, fxMatrix = null) {
  if (amount === null || amount === undefined || Number.isNaN(amount)) {
    return 0;
  }
  const from = (fromCurrency || "USD").toUpperCase();
  const to = (toCurrency || "USD").toUpperCase();

  // 1. Direct matrix lookup: always multiply rate (matrix[from][to] is 1.0 for same-to-same)
  if (
    fxMatrix &&
    fxMatrix[from] &&
    typeof fxMatrix[from][to] === "number" &&
    fxMatrix[from][to] > 0
  ) {
    return amount * fxMatrix[from][to];
  }
  // 2. Inverted matrix lookup: 1 / fxMatrix[to][from]
  if (
    fxMatrix &&
    fxMatrix[to] &&
    typeof fxMatrix[to][from] === "number" &&
    fxMatrix[to][from] > 0
  ) {
    return amount / fxMatrix[to][from];
  }
  // 3. Fallback triangulation via USD static table
  const fromRate = FX_RATES[from] ?? 1.0;
  const toRate = FX_RATES[to] ?? 1.0;
  return (amount / fromRate) * toRate;
}

/**
 * Backward-compatible helper using FX_RATES table.
 */
export function convertCurrency(amount, fromCurrency = "USD", toCurrency = "USD") {
  return convertAmount(amount, fromCurrency, toCurrency, {});
}

/**
 * Format a numeric value in currency (with symbol and 2 decimal places).
 */
export function formatMoney(amount, currency = "USD") {
  if (amount === null || amount === undefined || Number.isNaN(amount)) {
    return '<span class="muted">—</span>';
  }
  const targetCcy = (currency || "USD").toUpperCase();
  const absVal = Math.abs(amount);
  const sym = CURRENCY_SYMBOLS[targetCcy] ?? `${targetCcy} `;

  const numStr = absVal.toLocaleString("en-GB", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

  const formatted = `${sym}${numStr}`;
  return amount < 0 ? `-${formatted}` : formatted;
}

/**
 * Format signed money (+ or -) in currency with symbol.
 */
export function formatSignedMoney(amount, currency = "USD") {
  if (amount === null || amount === undefined || Number.isNaN(amount)) {
    return '<span class="muted">—</span>';
  }
  const targetCcy = (currency || "USD").toUpperCase();
  const absVal = Math.abs(amount);
  const sym = CURRENCY_SYMBOLS[targetCcy] ?? `${targetCcy} `;

  const numStr = absVal.toLocaleString("en-GB", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

  if (amount > 0.004) return `+${sym}${numStr}`;
  if (amount < -0.004) return `-${sym}${numStr}`;
  return `${sym}${numStr}`;
}

/**
 * Format percentage.
 */
export function formatPct(fraction, { signed = true, digits = 2 } = {}) {
  if (fraction === null || fraction === undefined || Number.isNaN(fraction)) {
    return '<span class="muted">—</span>';
  }
  const pctVal = fraction * 100;
  const absStr = Math.abs(pctVal).toFixed(digits) + "%";
  if (signed) {
    if (pctVal > 0.0001) return `+${absStr}`;
    if (pctVal < -0.0001) return `-${absStr}`;
  }
  return pctVal < 0 ? `-${absStr}` : absStr;
}

/**
 * Format quantity preserving exact full precision for fractional shares without display rounding.
 */
export function formatQty(value) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '<span class="muted">—</span>';
  }
  if (Number.isInteger(value)) {
    return value.toLocaleString("en-GB");
  }
  return value.toLocaleString("en-GB", { maximumFractionDigits: 20 });
}

/**
 * Return CSS class for positive / negative P&L.
 */
export function pnlClass(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "";
  if (value > 0.004) return "pos";
  if (value < -0.004) return "neg";
  return "";
}

/**
 * Escape text before inserting into innerHTML.
 */
export function esc(text) {
  if (text === null || text === undefined) return "";
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

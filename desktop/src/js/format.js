/**
 * Number and currency formatting helpers with dynamic FX rate support.
 */

export const FX_RATES = {
  USD: 1.0,
  HKD: 7.8413,
  EUR: 0.8913,
  GBP: 0.7435,
};

const CURRENCY_SYMBOLS = {
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
 * Convert an amount from fromCurrency to toCurrency via USD base rates.
 * FX_RATES stores 1 USD = rate * Currency (e.g. USD: 1.0, HKD: 7.84, EUR: 0.89).
 */
export function convertCurrency(amount, fromCurrency = "USD", toCurrency = "USD") {
  if (amount === null || amount === undefined || Number.isNaN(amount)) {
    return 0;
  }
  const fromCcy = (fromCurrency || "USD").toUpperCase();
  const toCcy = (toCurrency || "USD").toUpperCase();
  if (fromCcy === toCcy) {
    return amount;
  }
  const fromRate = FX_RATES[fromCcy] ?? 1.0;
  const toRate = FX_RATES[toCcy] ?? 1.0;
  // Convert from fromCcy to USD base, then from USD to toCcy
  return (amount / fromRate) * toRate;
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
 * Format quantity.
 */
export function formatQty(value) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '<span class="muted">—</span>';
  }
  return value.toLocaleString("en-GB", { maximumFractionDigits: 4 });
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

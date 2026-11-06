/**
 * Number and currency formatting helpers.
 *
 * Supports USD ($) and GBP (£) with a fixed FX rate of 0.7487.
 */

const FX_RATES = {
  USD: 1.0,
  GBP: 0.7487,
};

const CURRENCY_SYMBOLS = {
  USD: "$",
  GBP: "£",
};

/**
 * Format a USD-based numeric value into the active display currency.
 */
export function formatMoney(valInUsd, currency = "USD", { compact = false } = {}) {
  const rate = FX_RATES[currency] ?? 1.0;
  const sym = CURRENCY_SYMBOLS[currency] ?? "$";
  const converted = valInUsd * rate;
  const absVal = Math.abs(converted);

  const numStr = absVal.toLocaleString("en-GB", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

  const formatted = `${sym}${numStr}`;
  return converted < 0 ? `-${formatted}` : formatted;
}

/**
 * Format signed money (+ or -) with symbol.
 */
export function formatSignedMoney(valInUsd, currency = "USD") {
  const rate = FX_RATES[currency] ?? 1.0;
  const sym = CURRENCY_SYMBOLS[currency] ?? "$";
  const converted = valInUsd * rate;
  const absVal = Math.abs(converted);

  const numStr = absVal.toLocaleString("en-GB", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

  if (converted > 0.004) return `+${sym}${numStr}`;
  if (converted < -0.004) return `-${sym}${numStr}`;
  return `${sym}${numStr}`;
}

/**
 * Format percentage.
 */
export function formatPct(fraction, { signed = true, digits = 2 } = {}) {
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
  return value.toLocaleString("en-GB", { maximumFractionDigits: 4 });
}

/**
 * Return CSS class for positive / negative P&L.
 */
export function pnlClass(value) {
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

/** Number / money formatting helpers. */

const moneyFormatters = new Map();

export function money(value, currency = "USD", { compact = false } = {}) {
  const key = `${currency}|${compact}`;
  if (!moneyFormatters.has(key)) {
    moneyFormatters.set(
      key,
      new Intl.NumberFormat(undefined, {
        style: "currency",
        currency,
        notation: compact ? "compact" : "standard",
        maximumFractionDigits: compact ? 1 : 2,
        minimumFractionDigits: compact ? 0 : 2,
      }),
    );
  }
  return moneyFormatters.get(key).format(value);
}

export function signedMoney(value, currency = "USD") {
  const s = money(Math.abs(value), currency);
  return value > 0 ? `+${s}` : value < 0 ? `−${s}` : s;
}

export function pct(fraction, { signed = false, digits = 1 } = {}) {
  const s = `${(Math.abs(fraction) * 100).toFixed(digits)}%`;
  if (!signed) return fraction < 0 ? `−${s}` : s;
  return fraction > 0 ? `+${s}` : fraction < 0 ? `−${s}` : s;
}

export function qty(value) {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 4 }).format(value);
}

/** CSS class for coloring gains/losses. */
export function pnlClass(value) {
  return value > 0 ? "pos" : value < 0 ? "neg" : "";
}

/** Escape text before inserting it as HTML. */
export function esc(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

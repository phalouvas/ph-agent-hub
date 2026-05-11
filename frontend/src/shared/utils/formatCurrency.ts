// =============================================================================
// PH Agent Hub — Currency Formatter
// =============================================================================
// Reads the currency setting from the app settings and formats a numeric
// cost value accordingly. Falls back to EUR if setting is unavailable.
// =============================================================================

const CURRENCY_SYMBOLS: Record<string, string> = {
  EUR: "€",
  USD: "$",
  GBP: "£",
  JPY: "¥",
  CNY: "¥",
};

let _currencyCode = "EUR";

export function setCurrency(code: string): void {
  _currencyCode = code;
}

export function getCurrencyCode(): string {
  return _currencyCode;
}

export function formatCurrency(value: number | null | undefined): string {
  if (value == null || value === 0) return "-";
  const symbol = CURRENCY_SYMBOLS[_currencyCode] || _currencyCode;
  // Show 4 decimal places for sub-cent precision, but strip trailing zeros
  const formatted = value.toFixed(6).replace(/\.?0+$/, "");
  // Keep at least 2 decimal places
  const dotIndex = formatted.indexOf(".");
  if (dotIndex === -1) return `${symbol}${formatted}.00`;
  const decimals = formatted.length - dotIndex - 1;
  if (decimals === 1) return `${symbol}${formatted}0`;
  if (decimals === 0) return `${symbol}${formatted}.00`;
  return `${symbol}${formatted}`;
}

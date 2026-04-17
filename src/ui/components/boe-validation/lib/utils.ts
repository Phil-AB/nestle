/** Unwrap {value: ..., source: ...} envelopes or return raw value */
export function unwrap(v: any): string {
  if (v === null || v === undefined) return ""
  if (typeof v === "object" && "value" in v) return String(v.value ?? "")
  if (typeof v === "object") return JSON.stringify(v)
  return String(v)
}

/**
 * Format a discrepancy source_value / target_value for display.
 * Handles:
 *  - null / undefined → "—"
 *  - {value: ...} envelopes → unwrapped scalar
 *  - plain dicts (n-way matcher: {doc: val, ...}) → "doc1: val1 · doc2: val2"
 *  - arrays → joined with ", "
 *  - primitives → String()
 */
export function formatValue(v: any): string {
  if (v === null || v === undefined) return "—"
  // Unwrap confidence envelope
  if (typeof v === "object" && !Array.isArray(v) && "value" in v) {
    return String(v.value ?? "—")
  }
  if (Array.isArray(v)) {
    return v.map((item) => formatValue(item)).join(", ")
  }
  if (typeof v === "object") {
    // e.g. {bill_of_entry: "1901.90", invoice: "1901.9"} from n-way matcher
    // or   {invoice: "Nestlé SA", bill_of_lading: "Nestle S.A."} from shipper validator
    return Object.entries(v)
      .map(([doc, val]) => `${doc.replace(/_/g, " ")}: ${val}`)
      .join(" · ")
  }
  return String(v)
}

export function deriveConfidence(v: any): number {
  if (v === null || v === undefined) return 0
  if (typeof v === "object") {
    if (typeof v.confidence === "number") return Math.min(1, v.confidence)
    if (v.source === "ai_enhancement") return 0.92
    if (v.source === "direct") return 0.95
    return 0.85
  }
  return 0.85
}

/** Normalise a header or key string for fuzzy matching (snake_case, lowercase). */
export function normKey(s: string): string {
  return String(s).toLowerCase().replace(/[\s\-/\\]+/g, "_").replace(/[^\w]/g, "").replace(/_+/g, "_")
}

/** Unwrap {value: ..., source: ...} envelopes or return raw value */
export function unwrap(v: any): string {
  if (v === null || v === undefined) return ""
  if (typeof v === "object" && "value" in v) return String(v.value ?? "")
  if (Array.isArray(v)) return v.map((item) => unwrap(item)).join(", ")
  if (typeof v === "object") return JSON.stringify(v)
  return String(v)
}

/**
 * Format a discrepancy source_value / target_value for display.
 * Handles plain dicts (n-way matcher, shipper validator), {value} envelopes, arrays, and primitives.
 */
export function formatValue(v: any): string {
  if (v === null || v === undefined) return "—"
  if (typeof v === "object" && !Array.isArray(v) && "value" in v) {
    return String(v.value ?? "—")
  }
  if (Array.isArray(v)) {
    return v.map((item) => formatValue(item)).join(", ")
  }
  if (typeof v === "object") {
    return Object.entries(v)
      .map(([doc, val]) => `${doc.replace(/_/g, " ")}: ${val}`)
      .join(" · ")
  }
  return String(v)
}

/**
 * Derive a 0-1 confidence score from a raw field value.
 * - Fields wrapped with {source: "ai_enhancement"} → 0.92
 * - Direct plain values (extraction pass) → 0.85
 * - Fields with explicit confidence metadata → use that
 */
export function deriveConfidence(v: any): number {
  if (v === null || v === undefined) return 0
  if (typeof v === "object") {
    if (typeof v.confidence === "number") return Math.min(1, v.confidence)
    if (v.source === "ai_enhancement") return 0.92
    if (v.source === "direct") return 0.95
    return 0.85
  }
  // Plain scalar — came straight from the model
  return 0.85
}

/** Normalise a header or key string for fuzzy matching (snake_case, lowercase). */
export function normKey(s: string): string {
  return String(s).toLowerCase().replace(/[\s\-/\\]+/g, "_").replace(/[^\w]/g, "").replace(/_+/g, "_")
}

export function autoShipmentNumber(): string {
  const now = new Date()
  const ymd = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, "0")}${String(now.getDate()).padStart(2, "0")}`
  const rand = Math.random().toString(36).slice(2, 6).toUpperCase()
  return `SHP-${ymd}-${rand}`
}

/** Returns true when a raw field value carries a redaction flag */
export function isRedacted(v: any): boolean {
  return typeof v === "object" && v !== null && !Array.isArray(v) && v.redacted === true
}

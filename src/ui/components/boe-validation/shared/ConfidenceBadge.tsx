"use client"

export function ConfidenceBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100)
  const { label, color } =
    pct >= 80
      ? { label: "Confident",           color: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400" }
      : pct >= 51
      ? { label: "Partially Confident", color: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400" }
      : { label: "Not Confident",       color: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400" }
  return (
    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${color}`}>
      {label}
    </span>
  )
}

export function SeverityBadge({ severity }: { severity: string }) {
  const map: Record<string, string> = {
    critical: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
    major: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
    minor: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-500",
    info: "bg-muted text-muted-foreground",
  }
  return (
    <span
      className={`text-[10px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded ${
        map[severity] ?? map.info
      }`}
    >
      {severity}
    </span>
  )
}

"use client"

import type { LucideIcon } from "lucide-react"

export interface TabDef<T extends string> {
  v: T
  label: string
  icon: LucideIcon
  count?: number
}

interface TabBarProps<T extends string> {
  tabs: TabDef<T>[]
  active: T
  onChange: (v: T) => void
}

export function TabBar<T extends string>({ tabs, active, onChange }: TabBarProps<T>) {
  return (
    <div className="flex justify-center py-1">
      <div className="flex items-center bg-muted/70 rounded-xl p-1 gap-0.5 border border-border/50 shadow-sm">
        {tabs.map(({ v, label, icon: Icon, count }) => (
          <button
            key={v}
            onClick={() => onChange(v)}
            className={`flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-medium transition-all duration-150 ${
              active === v
                ? "bg-background text-foreground shadow-sm border border-border/60"
                : "text-muted-foreground hover:text-foreground hover:bg-background/50"
            }`}
          >
            <Icon className={`w-3.5 h-3.5 ${active === v ? "text-primary" : ""}`} />
            {label}
            {count !== undefined && (
              <span className={`text-[11px] font-bold px-1.5 py-0.5 rounded-md ${active === v ? "bg-primary/10 text-primary" : "bg-muted-foreground/15 text-muted-foreground"}`}>
                {count}
              </span>
            )}
          </button>
        ))}
      </div>
    </div>
  )
}

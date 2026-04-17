"use client"

import { Check } from "lucide-react"
import type { Step } from "../lib/types"

const STEP_ORDER: Step[] = ["upload", "field_review", "review", "complete"]
const STEP_LABELS: Record<string, string> = {
  upload: "Upload",
  field_review: "Review Fields",
  review: "Discrepancies",
  complete: "Complete",
}

interface StepIndicatorProps {
  step: Step
}

export function StepIndicator({ step }: StepIndicatorProps) {
  return (
    <div className="flex items-center gap-2 mb-6">
      {(["upload", "field_review", "review", "complete"] as const).map((s, i) => {
        const currentIdx = STEP_ORDER.indexOf(step === "processing" ? "field_review" : step)
        const thisIdx = STEP_ORDER.indexOf(s)
        const done = thisIdx < currentIdx
        const active = thisIdx === currentIdx
        return (
          <div key={s} className="flex items-center gap-2">
            <div className={`flex items-center gap-1.5 text-xs font-medium ${active ? "text-primary" : done ? "text-green-600 dark:text-green-400" : "text-muted-foreground"}`}>
              <div className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold border-2 ${active ? "border-primary bg-primary text-primary-foreground" : done ? "border-green-500 bg-green-500 text-white" : "border-muted-foreground/30"}`}>
                {done ? <Check className="w-3 h-3" /> : i + 1}
              </div>
              {STEP_LABELS[s]}
            </div>
            {i < 3 && <div className={`w-8 h-px ${done ? "bg-green-400" : "bg-border"}`} />}
          </div>
        )
      })}
    </div>
  )
}

"use client"

import { Check } from "lucide-react"
import { INDICATOR_STEPS, STEP_ORDER } from "../lib/constants"
import type { Step } from "../lib/types"

interface StepIndicatorProps {
  step: Step
}

export function StepIndicator({ step }: StepIndicatorProps) {
  const currentIdx = STEP_ORDER.indexOf(step === "processing" ? "field_review" : step)

  return (
    <div className="flex items-center gap-2 mb-6">
      {INDICATOR_STEPS.map(({ key, label }, i) => {
        const thisIdx = STEP_ORDER.indexOf(key)
        const done = thisIdx < currentIdx
        const active = thisIdx === currentIdx
        return (
          <div key={key} className="flex items-center gap-2">
            <div
              className={`flex items-center gap-1.5 text-xs font-medium ${
                active
                  ? "text-primary"
                  : done
                  ? "text-green-600 dark:text-green-400"
                  : "text-muted-foreground"
              }`}
            >
              <div
                className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold border-2 ${
                  active
                    ? "border-primary bg-primary text-primary-foreground"
                    : done
                    ? "border-green-500 bg-green-500 text-white"
                    : "border-muted-foreground/30"
                }`}
              >
                {done ? <Check className="w-3 h-3" /> : i + 1}
              </div>
              {label}
            </div>
            {i < INDICATOR_STEPS.length - 1 && (
              <div className={`w-8 h-px ${done ? "bg-green-400" : "bg-border"}`} />
            )}
          </div>
        )
      })}
    </div>
  )
}

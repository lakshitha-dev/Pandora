"use client"

import { cn } from "@/lib/utils"
import { EVIDENCE_META, type EvidenceQuality } from "./data"

const toneMap = {
  green: {
    text: "text-secondary",
    border: "border-secondary/40",
    bg: "bg-secondary/10",
    glow: "text-glow-green",
  },
  amber: {
    text: "text-warning",
    border: "border-warning/40",
    bg: "bg-warning/10",
    glow: "",
  },
  red: {
    text: "text-critical",
    border: "border-critical/40",
    bg: "bg-critical/10",
    glow: "",
  },
} as const

export function EvidenceBadge({
  quality,
  className,
}: {
  quality: EvidenceQuality
  className?: string
}) {
  const meta = EVIDENCE_META[quality]
  const tone = toneMap[meta.tone]

  return (
    <span className={cn("group relative inline-flex", className)}>
      <span
        className={cn(
          "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium",
          tone.text,
          tone.border,
          tone.bg,
        )}
      >
        <span aria-hidden className={cn("font-display font-bold leading-none", tone.glow)}>
          {meta.symbol}
        </span>
        {meta.label}
      </span>
      {/* tooltip */}
      <span
        role="tooltip"
        className="pointer-events-none absolute bottom-full left-1/2 z-30 mb-2 w-56 -translate-x-1/2 rounded-lg border border-border-glow bg-surface-2 p-2.5 text-xs leading-relaxed text-muted-foreground opacity-0 shadow-xl transition-opacity duration-200 group-hover:opacity-100"
      >
        <span className={cn("mb-0.5 block font-medium", tone.text)}>{meta.label}</span>
        {meta.tip}
      </span>
    </span>
  )
}

export function Tag({
  children,
  tone = "cyan",
}: {
  children: React.ReactNode
  tone?: "cyan" | "purple" | "green"
}) {
  const map = {
    cyan: "border-primary/30 text-primary bg-primary/5",
    purple: "border-accent/40 text-accent bg-accent/10",
    green: "border-secondary/30 text-secondary bg-secondary/5",
  } as const
  return (
    <span className={cn("inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-medium", map[tone])}>
      {children}
    </span>
  )
}

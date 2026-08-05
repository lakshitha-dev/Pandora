"use client"

import { useEffect, useRef, useState } from "react"
import {
  ArrowUp,
  Mic,
  Network,
  TriangleAlert,
  ChevronDown,
  CircleCheck,
  Loader2,
  ShieldQuestion,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { EvidenceBadge } from "./badges"
import {
  EMERGENCY_META,
  ROLE_INTRO,
  SUGGESTED_QUESTIONS,
  type Answer,
  type Role,
} from "./data"

const STEPS = ["Searching knowledge base...", "Retrieving relevant chunks...", "Generating grounded answer..."]

function WelcomeState({ onPick }: { onPick: (q: string) => void }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center px-6 py-10 text-center">
      <span className="mb-6 flex h-20 w-20 items-center justify-center rounded-full border border-primary/40 bg-primary/10 text-primary glow-cyan-strong">
        <Network className="h-9 w-9" />
      </span>
      <h2 className="font-display text-2xl font-bold tracking-wide text-foreground text-glow-cyan">
        Ask the Living Network
      </h2>
      <p className="mt-3 max-w-md text-balance text-sm leading-relaxed text-muted-foreground">
        Query Pandora&apos;s environmental knowledge base. Every answer is grounded in retrieved documents.
      </p>
      <div className="mt-7 grid w-full max-w-lg grid-cols-1 gap-2.5 sm:grid-cols-2">
        {SUGGESTED_QUESTIONS.map((q) => (
          <button
            key={q}
            onClick={() => onPick(q)}
            className="rounded-xl border border-border bg-surface-2 px-4 py-3 text-left text-xs leading-relaxed text-muted-foreground transition-all hover:scale-[1.03] hover:border-primary/60 hover:text-foreground hover:glow-cyan"
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  )
}

function ProcessingSteps({ step }: { step: number }) {
  return (
    <div className="rounded-2xl border border-border bg-surface p-5">
      <div className="mb-4 flex items-center gap-2 text-xs font-medium uppercase tracking-widest text-primary">
        <Loader2 className="h-4 w-4 animate-spin" />
        Assembling situation report
      </div>
      <ol className="flex flex-col gap-3">
        {STEPS.map((label, i) => {
          const done = i < step
          const current = i === step
          return (
            <li key={label} className="flex items-center gap-3 text-sm">
              <span
                className={cn(
                  "flex h-6 w-6 items-center justify-center rounded-full border transition-all",
                  done && "border-secondary bg-secondary/15 text-secondary glow-green",
                  current && "border-primary bg-primary/15 text-primary glow-cyan",
                  !done && !current && "border-border text-muted-foreground",
                )}
              >
                {done ? (
                  <CircleCheck className="h-3.5 w-3.5" />
                ) : current ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <span className="text-[10px]">{i + 1}</span>
                )}
              </span>
              <span className={cn(done ? "text-foreground" : current ? "text-primary" : "text-muted-foreground")}>
                {label}
              </span>
            </li>
          )
        })}
      </ol>
    </div>
  )
}

function ConflictBanner({ conflict }: { conflict: NonNullable<Answer["conflict"]> }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="overflow-hidden rounded-xl border border-warning/50 bg-warning/10">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2.5 px-4 py-3 text-left"
      >
        <TriangleAlert className="h-4 w-4 shrink-0 text-warning" />
        <span className="flex-1 text-sm font-semibold text-warning">Conflicting Evidence Detected</span>
        <ChevronDown className={cn("h-4 w-4 text-warning transition-transform", open && "rotate-180")} />
      </button>
      <p className="px-4 pb-3 text-xs leading-relaxed text-warning/90">{conflict.summary}</p>
      {open && (
        <div className="grid grid-cols-1 gap-3 border-t border-warning/30 p-3 sm:grid-cols-2">
          {[conflict.a, conflict.b].map((c) => (
            <div key={c.label} className="rounded-lg border border-border bg-surface-2 p-3">
              <p className="mb-1 text-[11px] font-semibold text-primary">{c.label}</p>
              <p className="text-xs leading-relaxed text-muted-foreground">{c.text}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function AnswerBubble({ answer, role }: { answer: Answer; role: Role }) {
  const emergency = EMERGENCY_META[answer.emergency]
  return (
    <div className="relative max-w-2xl rounded-2xl rounded-tl-sm border border-border bg-surface p-5">
      {/* glowing top-left corner accent */}
      <span className="absolute left-0 top-0 h-8 w-8 rounded-tl-2xl border-l-2 border-t-2 border-primary" style={{ boxShadow: "-2px -2px 16px rgba(0,229,255,0.4)" }} />

      <p className="mb-3 text-sm leading-relaxed text-muted-foreground">{ROLE_INTRO[role]}</p>

      <p className="mb-2 text-sm font-medium text-foreground">
        Possible causes of the turquoise water near <strong className="text-primary">Awa Reef</strong>:
      </p>
      <ul className="mb-4 flex flex-col gap-2.5">
        {answer.causes.map((c) => (
          <li key={c.term} className="flex gap-2.5 text-sm leading-relaxed text-muted-foreground">
            <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-primary glow-cyan" />
            <span>
              <strong className="text-foreground">{c.term}.</strong> {c.detail}
            </span>
          </li>
        ))}
      </ul>

      {answer.conflict && <ConflictBanner conflict={answer.conflict} />}

      <div className="mt-4 flex flex-wrap items-center gap-2.5">
        <EvidenceBadge quality={answer.quality} />
        <span
          className={cn(
            "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium",
            "border-warning/50 bg-warning/10 text-warning glow-amber",
          )}
        >
          {emergency.label}
        </span>
      </div>
    </div>
  )
}

export function CenterPanel({
  role,
  query,
  answer,
  processing,
  step,
  input,
  setInput,
  onSubmit,
  onPick,
}: {
  role: Role
  query: string | null
  answer: Answer | null
  processing: boolean
  step: number
  input: string
  setInput: (v: string) => void
  onSubmit: () => void
  onPick: (q: string) => void
}) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const [sent, setSent] = useState(false)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" })
  }, [query, processing, step, answer])

  const handleSend = () => {
    if (!input.trim()) return
    setSent(true)
    setTimeout(() => setSent(false), 600)
    onSubmit()
  }

  return (
    <div className="flex h-full flex-col">
      {/* Top bar */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-5 py-3">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span className="capitalize text-primary">{role}</span>
          <span className="text-border-glow">/</span>
          <span>Ecosystem Intelligence Interface</span>
        </div>
        <div className="flex items-center gap-2 rounded-full border border-secondary/30 bg-secondary/5 px-3 py-1 text-[11px] text-secondary">
          <span className="h-1.5 w-1.5 rounded-full bg-secondary glow-green" />
          Knowledge Base: Active · 56 pages indexed
        </div>
      </div>

      {/* processing progress bar */}
      {processing && (
        <div className="relative h-0.5 w-full overflow-hidden bg-primary/10 progress-shimmer" />
      )}

      {/* Conversation */}
      <div ref={scrollRef} className="flex flex-1 flex-col gap-5 overflow-y-auto px-5 py-6 thin-scroll">
        {!query && !processing && <WelcomeState onPick={onPick} />}

        {query && (
          <div className="flex justify-end">
            <div className="max-w-lg rounded-2xl rounded-tr-sm border-l-2 border-primary/60 bg-surface-2 px-4 py-3 text-sm leading-relaxed text-foreground">
              {query}
            </div>
          </div>
        )}

        {processing && (
          <div className="flex justify-start">
            <ProcessingSteps step={step} />
          </div>
        )}

        {!processing && answer && (
          <div className="flex justify-start">
            <AnswerBubble answer={answer} role={role} />
          </div>
        )}
      </div>

      {/* Input area */}
      <div className="border-t border-border bg-surface/60 px-5 py-4 backdrop-blur-md">
        <div className="flex items-center gap-2 rounded-2xl border border-border bg-surface-2 px-3 py-2 transition-all focus-within:border-primary/60 focus-within:glow-cyan">
          <button className="rounded-lg p-2 text-muted-foreground transition-colors hover:text-primary" aria-label="Voice input">
            <Mic className="h-4.5 w-4.5" />
          </button>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.nativeEvent.isComposing && (e as any).keyCode !== 229) {
                e.preventDefault()
                handleSend()
              }
            }}
            placeholder="Ask about Pandora's ecosystems, species, emergencies, or conservation..."
            className="flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground/70 focus:outline-none"
          />
          <button
            onClick={handleSend}
            aria-label="Send"
            className={cn(
              "flex h-9 w-9 items-center justify-center rounded-xl border border-primary bg-primary/15 text-primary transition-all hover:glow-cyan-strong",
              sent && "animate-send-pulse",
            )}
          >
            <ArrowUp className="h-4.5 w-4.5" />
          </button>
        </div>
        <p className="mt-2 flex items-center gap-1.5 px-1 text-[11px] text-muted-foreground">
          <ShieldQuestion className="h-3.5 w-3.5" />
          Answers are grounded in retrieved documents only · Sources shown below each response
        </p>
      </div>
    </div>
  )
}

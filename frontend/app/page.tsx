"use client"

import { useCallback, useRef, useState } from "react"
import { ChevronDown, X } from "lucide-react"
import { cn } from "@/lib/utils"
import { Particles } from "@/components/pandora/particles"
import { TopNav } from "@/components/pandora/top-nav"
import { LeftSidebar } from "@/components/pandora/left-sidebar"
import { CenterPanel } from "@/components/pandora/center-panel"
import { RightPanel } from "@/components/pandora/right-panel"
import { SAMPLE_ANSWER, type Answer, type Role } from "@/components/pandora/data"

export default function Page() {
  const [role, setRole] = useState<Role>("guardian")
  const [query, setQuery] = useState<string | null>(SAMPLE_ANSWER.question)
  const [answer, setAnswer] = useState<Answer | null>(SAMPLE_ANSWER)
  const [processing, setProcessing] = useState(false)
  const [step, setStep] = useState(0)
  const [input, setInput] = useState("")
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [sourcesOpen, setSourcesOpen] = useState(true)
  const timers = useRef<ReturnType<typeof setTimeout>[]>([])

  const runQuery = useCallback((q: string) => {
    timers.current.forEach(clearTimeout)
    timers.current = []
    setQuery(q)
    setAnswer(null)
    setProcessing(true)
    setStep(0)
    setInput("")
    ;[0, 1, 2].forEach((s) => {
      timers.current.push(setTimeout(() => setStep(s), s * 700))
    })
    timers.current.push(
      setTimeout(() => {
        setProcessing(false)
        setAnswer({ ...SAMPLE_ANSWER, question: q })
      }, 2400),
    )
  }, [])

  const handleSubmit = () => {
    if (!input.trim()) return
    runQuery(input.trim())
  }

  const handleNewSession = () => {
    timers.current.forEach(clearTimeout)
    timers.current = []
    setQuery(null)
    setAnswer(null)
    setProcessing(false)
    setStep(0)
    setInput("")
  }

  return (
    <div className="relative flex h-screen flex-col overflow-hidden bg-background text-foreground">
      <Particles />

      <div className="relative z-10 flex h-full flex-col">
        <TopNav onNewSession={handleNewSession} onToggleSidebar={() => setSidebarOpen((o) => !o)} />

        <div className="flex min-h-0 flex-1">
          {/* Left sidebar - desktop */}
          <aside className="hidden w-[280px] shrink-0 border-r border-border bg-surface/40 backdrop-blur-md lg:block">
            <LeftSidebar role={role} onRoleChange={setRole} />
          </aside>

          {/* Center */}
          <main className="flex min-w-0 flex-1 flex-col">
            <CenterPanel
              role={role}
              query={query}
              answer={answer}
              processing={processing}
              step={step}
              input={input}
              setInput={setInput}
              onSubmit={handleSubmit}
              onPick={runQuery}
            />

            {/* Right panel as accordion on mobile / tablet */}
            <div className="border-t border-border bg-surface/40 xl:hidden">
              <button
                onClick={() => setSourcesOpen((o) => !o)}
                className="flex w-full items-center justify-between px-5 py-3 text-sm font-semibold text-foreground"
              >
                Retrieved Sources & Analysis
                <ChevronDown className={cn("h-4 w-4 text-primary transition-transform", sourcesOpen && "rotate-180")} />
              </button>
              {sourcesOpen && (
                <div className="max-h-[70vh] overflow-hidden">
                  <RightPanel answer={answer} />
                </div>
              )}
            </div>
          </main>

          {/* Right sidebar - desktop */}
          <aside className="hidden w-[320px] shrink-0 border-l border-border bg-surface/40 backdrop-blur-md xl:block">
            <RightPanel answer={answer} />
          </aside>
        </div>
      </div>

      {/* Mobile sidebar bottom sheet */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div
            className="absolute inset-0 bg-background/70 backdrop-blur-sm"
            onClick={() => setSidebarOpen(false)}
          />
          <div className="absolute inset-x-0 bottom-0 max-h-[85vh] overflow-hidden rounded-t-2xl border-t border-border-glow bg-surface glow-cyan">
            <div className="flex items-center justify-between border-b border-border px-4 py-3">
              <span className="mx-auto h-1 w-10 rounded-full bg-border-glow" />
              <button
                onClick={() => setSidebarOpen(false)}
                aria-label="Close"
                className="text-muted-foreground hover:text-primary"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="max-h-[calc(85vh-56px)] overflow-y-auto thin-scroll">
              <LeftSidebar role={role} onRoleChange={(r) => setRole(r)} />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

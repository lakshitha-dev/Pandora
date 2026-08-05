"use client"

import { Network, Plus, Settings, Menu } from "lucide-react"

export function TopNav({
  onNewSession,
  onToggleSidebar,
}: {
  onNewSession: () => void
  onToggleSidebar: () => void
}) {
  return (
    <header className="relative z-20 flex h-14 items-center justify-between border-b border-border bg-surface/70 px-4 backdrop-blur-md">
      <div className="flex items-center gap-2">
        <button
          onClick={onToggleSidebar}
          className="mr-1 rounded-md p-2 text-muted-foreground transition-colors hover:text-primary lg:hidden"
          aria-label="Toggle sidebar"
        >
          <Menu className="h-5 w-5" />
        </button>
        <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-primary/40 bg-primary/10 text-primary glow-cyan">
          <Network className="h-4 w-4" />
        </span>
      </div>

      <h1 className="pointer-events-none absolute left-1/2 hidden -translate-x-1/2 items-center font-display text-sm font-bold tracking-[0.35em] text-primary text-glow-cyan sm:flex">
        PANDORA KNOWLEDGE GUARDIAN
      </h1>

      <div className="flex items-center gap-2">
        <button
          onClick={onNewSession}
          className="hidden items-center gap-1.5 rounded-lg border border-primary/40 px-3 py-1.5 text-xs font-medium text-primary transition-all hover:bg-primary/10 hover:glow-cyan sm:flex"
        >
          <Plus className="h-3.5 w-3.5" />
          New Session
        </button>
        <button
          className="rounded-md p-2 text-muted-foreground transition-colors hover:text-primary"
          aria-label="Settings"
        >
          <Settings className="h-4.5 w-4.5" />
        </button>
        <span
          aria-hidden
          className="flex h-8 w-8 items-center justify-center rounded-full border border-border-glow bg-gradient-to-br from-primary/30 to-accent/30 text-xs font-semibold text-foreground"
        >
          GX
        </span>
      </div>
    </header>
  )
}

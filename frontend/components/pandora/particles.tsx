"use client"

import { useEffect, useState } from "react"

interface Dot {
  id: number
  left: number
  size: number
  delay: number
  duration: number
  green: boolean
}

export function Particles({ count = 26 }: { count?: number }) {
  // Generate on the client only, after mount, to avoid a hydration mismatch
  // (Math.random() would produce different server/client HTML).
  const [dots, setDots] = useState<Dot[]>([])

  useEffect(() => {
    setDots(
      Array.from({ length: count }).map((_, i) => ({
        id: i,
        left: Math.random() * 100,
        size: 1.5 + Math.random() * 3,
        delay: Math.random() * 18,
        duration: 16 + Math.random() * 16,
        green: i % 4 === 0,
      })),
    )
  }, [count])

  return (
    <div aria-hidden="true" className="pointer-events-none fixed inset-0 overflow-hidden">
      {/* deep ocean radial gradient */}
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(120% 80% at 50% -10%, rgba(0,229,255,0.10), transparent 55%), radial-gradient(90% 70% at 85% 110%, rgba(57,255,143,0.06), transparent 60%), radial-gradient(70% 60% at 10% 100%, rgba(168,85,247,0.06), transparent 60%)",
        }}
      />
      {dots.map((d) => (
        <span
          key={d.id}
          className="animate-float absolute bottom-0 rounded-full"
          style={{
            left: `${d.left}%`,
            width: d.size,
            height: d.size,
            animationDelay: `${d.delay}s`,
            animationDuration: `${d.duration}s`,
            background: d.green ? "rgba(57,255,143,0.7)" : "rgba(0,229,255,0.7)",
            boxShadow: d.green ? "0 0 8px rgba(57,255,143,0.8)" : "0 0 8px rgba(0,229,255,0.8)",
          }}
        />
      ))}
    </div>
  )
}

import { Analytics } from '@vercel/analytics/next'
import type { Metadata, Viewport } from 'next'
import { Inter, Orbitron } from 'next/font/google'
import './globals.css'

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
})

const orbitron = Orbitron({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700', '800', '900'],
  variable: '--font-orbitron',
})

export const metadata: Metadata = {
  title: 'Pandora Knowledge Guardian',
  description:
    'An AI-powered RAG knowledge guardian for the bioluminescent moon of Pandora — grounded answers, retrieved sources, and honest uncertainty for environmental researchers, guardians, and citizens.',
  generator: 'v0.app',
}

export const viewport: Viewport = {
  colorScheme: 'dark',
  themeColor: '#050d1a',
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    // suppressHydrationWarning covers only these two elements' own attributes, so
    // extensions that inject attributes on <html>/<body> before React hydrates
    // (Grammarly, dark-mode and password managers all do) stop throwing. Real
    // mismatches anywhere below still surface — React does not suppress deeply.
    <html
      lang="en"
      className={`${inter.variable} ${orbitron.variable} bg-background`}
      suppressHydrationWarning
    >
      <body className="antialiased font-sans" suppressHydrationWarning>
        {children}
        {process.env.NODE_ENV === 'production' && <Analytics />}
      </body>
    </html>
  )
}

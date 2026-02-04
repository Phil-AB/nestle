import type React from "react"
import type { Metadata } from "next"
import { Geist, Geist_Mono } from "next/font/google"
import { Analytics } from "@vercel/analytics/next"
import "./globals.css"
import Sidebar from "@/components/sidebar"
import { Toaster } from "@/components/ui/toaster"
import Providers from "@/components/providers"

const _geist = Geist({ subsets: ["latin"] })
const _geistMono = Geist_Mono({ subsets: ["latin"] })

// <CHANGE> Updated metadata for document processing dashboard
export const metadata: Metadata = {
  title: "Document Processing Dashboard",
  description: "Enterprise document management and shipment tracking system",
  generator: "v0.app",
  icons: {
    icon: [
      {
        url: "/icon-light-32x32.png",
        media: "(prefers-color-scheme: light)",
      },
      {
        url: "/icon-dark-32x32.png",
        media: "(prefers-color-scheme: dark)",
      },
      {
        url: "/icon.svg",
        type: "image/svg+xml",
      },
    ],
    apple: "/apple-icon.png",
  },
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en">
      <body className={`font-sans antialiased`}>
        <Providers>
          <div className="flex h-screen bg-background">
            <Sidebar />
            <main className="flex-1 overflow-auto">{children}</main>
          </div>
          <Toaster />
          <Analytics />
        </Providers>
      </body>
    </html>
  )
}

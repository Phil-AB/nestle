"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { Settings, LogOut, ShieldCheck, FileSearch, LayoutDashboard } from "lucide-react"

// Nestle brand brown (#63513D) and derivatives
const BRAND = "#63513D"
const BRAND_DARK = "#4A3B2E"
const BRAND_LIGHT = "#8B7355"
const BRAND_CREAM = "#F5F0EB"

export default function Sidebar() {
  const pathname = usePathname()

  const navItems = [
    { href: "/", icon: LayoutDashboard, label: "Dashboard" },
    { href: "/validation/vendor-docs", icon: ShieldCheck, label: "Vendor Validation" },
    { href: "/validation/boe", icon: FileSearch, label: "BOE Validation" },
  ]

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href)

  return (
    <aside
      className="w-64 flex flex-col border-r"
      style={{
        background: `linear-gradient(180deg, ${BRAND_DARK} 0%, ${BRAND} 100%)`,
        borderColor: BRAND_DARK,
      }}
    >
      {/* Header */}
      <div className="p-5 border-b" style={{ borderColor: BRAND_LIGHT + "40" }}>
        <div className="flex items-center">
          <img src="/nestle.svg" alt="Nestle" className="w-full h-auto brightness-0 invert opacity-90" />
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-1">
        {navItems.map((item) => {
          const Icon = item.icon
          const active = isActive(item.href)
          return (
            <Link
              key={item.href}
              href={item.href}
              className="flex items-center gap-3 px-4 py-2.5 rounded-lg transition-all duration-150"
              style={{
                background: active ? BRAND_CREAM : "transparent",
                color: active ? BRAND_DARK : BRAND_CREAM + "CC",
                fontWeight: active ? 600 : 400,
              }}
              onMouseEnter={(e) => {
                if (!active) {
                  e.currentTarget.style.background = BRAND_LIGHT + "30"
                  e.currentTarget.style.color = BRAND_CREAM
                }
              }}
              onMouseLeave={(e) => {
                if (!active) {
                  e.currentTarget.style.background = "transparent"
                  e.currentTarget.style.color = BRAND_CREAM + "CC"
                }
              }}
            >
              <Icon className="w-5 h-5" />
              <span className="text-sm">{item.label}</span>
            </Link>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="p-4 space-y-1" style={{ borderTop: `1px solid ${BRAND_LIGHT}40` }}>
        <button
          className="w-full flex items-center gap-3 px-4 py-2.5 rounded-lg transition-all duration-150"
          style={{ color: BRAND_CREAM + "CC" }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = BRAND_LIGHT + "30"
            e.currentTarget.style.color = BRAND_CREAM
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "transparent"
            e.currentTarget.style.color = BRAND_CREAM + "CC"
          }}
        >
          <Settings className="w-5 h-5" />
          <span className="text-sm">Settings</span>
        </button>
        <button
          className="w-full flex items-center gap-3 px-4 py-2.5 rounded-lg transition-all duration-150"
          style={{ color: BRAND_CREAM + "CC" }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = BRAND_LIGHT + "30"
            e.currentTarget.style.color = BRAND_CREAM
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "transparent"
            e.currentTarget.style.color = BRAND_CREAM + "CC"
          }}
        >
          <LogOut className="w-5 h-5" />
          <span className="text-sm">Logout</span>
        </button>
      </div>
    </aside>
  )
}

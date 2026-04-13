"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { Upload, Settings, LogOut, FileOutput, ShieldCheck, FileSearch, LayoutDashboard } from "lucide-react"

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
    <aside className="w-64 bg-card border-r border-border flex flex-col">
      {/* Header */}
      <div className="p-6 border-b border-border">
        <div className="flex items-center">
          <img src="/nestle.png" alt="Nestle" className="w-full h-auto" />
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-2">
        {navItems.map((item) => {
          const Icon = item.icon
          const active = isActive(item.href)
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${active ? "bg-primary text-primary-foreground" : "text-foreground hover:bg-muted"
                }`}
            >
              <Icon className="w-5 h-5" />
              <span className="font-medium">{item.label}</span>
            </Link>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-border space-y-2">
        <button className="w-full flex items-center gap-3 px-4 py-3 rounded-lg text-foreground hover:bg-muted transition-colors">
          <Settings className="w-5 h-5" />
          <span className="font-medium">Settings</span>
        </button>
        <button className="w-full flex items-center gap-3 px-4 py-3 rounded-lg text-foreground hover:bg-muted transition-colors">
          <LogOut className="w-5 h-5" />
          <span className="font-medium">Logout</span>
        </button>
      </div>
    </aside>
  )
}

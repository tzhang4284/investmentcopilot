"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/", label: "Dashboard", icon: "◈" },
  { href: "/portfolio", label: "Portfolio", icon: "▤" },
  { href: "/stock", label: "Stocks", icon: "↗" },
  { href: "/comps", label: "Comps", icon: "⇄" },
  { href: "/insiders", label: "Insiders", icon: "👁" },
  { href: "/theses", label: "Theses", icon: "✎" },
  { href: "/chat", label: "AI Analyst", icon: "✦" },
];

export default function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="w-52 shrink-0 border-r border-edge bg-surface min-h-screen sticky top-0 flex flex-col">
      <div className="px-5 py-6">
        <Link href="/" className="block">
          <div className="text-lg font-semibold tracking-tight">
            Investment<span className="text-accent">Copilot</span>
          </div>
          <div className="text-xs text-muted mt-0.5">You are the PM</div>
        </Link>
      </div>
      <nav className="flex-1 px-3 space-y-1">
        {NAV.map((item) => {
          const active =
            item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors ${
                active
                  ? "bg-edge text-foreground font-medium"
                  : "text-muted hover:text-foreground hover:bg-edge/50"
              }`}
            >
              <span className="w-4 text-center">{item.icon}</span>
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="px-5 py-4 text-[10px] text-muted border-t border-edge">
        Data: yfinance + SEC EDGAR
        <br />
        Not investment advice
      </div>
    </aside>
  );
}

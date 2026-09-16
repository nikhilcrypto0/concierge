"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  { href: "/", label: "Customer site" },
  { href: "/console", label: "Support console" },
] as const;

export function DemoBar() {
  const pathname = usePathname();

  return (
    <div className="border-b border-ink-900/15 bg-ink-950 text-sand-50">
      <div className="mx-auto flex w-full max-w-7xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-2 sm:px-6">
        <span className="flex items-center gap-2 text-sm font-semibold tracking-tight">
          Concierge
          <span className="rounded-full bg-tide-600/20 px-2 py-0.5 text-[11px] font-medium text-tide-100 ring-1 ring-inset ring-tide-600/40">
            demo
          </span>
        </span>

        <nav aria-label="Demo views" className="flex items-center gap-1">
          {TABS.map((tab) => {
            const active = pathname === tab.href;
            return (
              <Link
                key={tab.href}
                href={tab.href}
                aria-current={active ? "page" : undefined}
                className={`rounded-full px-3 py-1 text-sm transition-colors ${
                  active
                    ? "bg-sand-50 text-ink-950"
                    : "text-sand-200 hover:bg-white/10 hover:text-sand-50"
                }`}
              >
                {tab.label}
              </Link>
            );
          })}
        </nav>

        <a
          href="https://github.com/nikhilcrypto0/concierge"
          target="_blank"
          rel="noreferrer"
          className="ml-auto rounded-full px-3 py-1 text-sm text-sand-200 underline-offset-4 hover:text-sand-50 hover:underline"
        >
          Source
        </a>
      </div>
    </div>
  );
}

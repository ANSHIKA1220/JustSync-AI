"use client";

import { getOrganization, getUser, type Organization } from "@/lib/api";
import { BarChart3, BookOpen, Bot, ClipboardList, GitBranch, Inbox, LogOut, Map, MessageSquare, Route, Settings, ShieldCheck, UserRound } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AIProviderBadge, SystemStatusPopover } from "./provider-status";

const nav = [
  { href: "/dashboard", label: "Dashboard", icon: BarChart3, roles: ["administrator", "agent"] },
  { href: "/inbox", label: "Inbox", icon: Inbox, roles: ["administrator", "agent"] },
  { href: "/workspace", label: "Workspace", icon: Bot, roles: ["administrator", "agent"] },
  { href: "/customer-360", label: "Customer 360", icon: UserRound, roles: ["administrator", "agent"] },
  { href: "/journey-map", label: "Journey Map", icon: Map, roles: ["administrator", "agent"] },
  { href: "/knowledge", label: "Knowledge", icon: BookOpen, roles: ["administrator"] },
  { href: "/analytics", label: "Analytics", icon: ClipboardList, roles: ["administrator", "agent"] },
  { href: "/routing", label: "Routing", icon: Route, roles: ["administrator"] },
  { href: "/audit", label: "AI Transparency", icon: ShieldCheck, roles: ["administrator", "agent"] },
  { href: "/settings", label: "Settings", icon: Settings, roles: ["administrator"] },
  { href: "/simulator", label: "Chat Simulator", icon: MessageSquare, roles: ["administrator", "agent", "customer"] }
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState(getUser());
  const [organization, setOrganization] = useState<Organization | null>(null);
  const pathname = usePathname();
  const router = useRouter();
  useEffect(() => {
    const stored = getUser();
    setUser(stored);
    if (stored) getOrganization().then(setOrganization).catch(() => setOrganization(null));
  }, []);
  const visible = nav.filter((item) => !user || item.roles.includes(user.role));
  return (
    <div className="min-h-screen bg-mist">
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-64 border-r border-slate-200 bg-white p-4 lg:block">
        <Link href="/" className="flex items-center gap-3 rounded-lg px-2 py-3">
          <span className="flex size-10 items-center justify-center rounded-md bg-navy text-white"><GitBranch className="size-5" /></span>
          <span><b>JourneySync AI</b><span className="mt-1 block"><AIProviderBadge compact /></span></span>
        </Link>
        <div className="mt-3 rounded-md border border-slate-200 bg-slate-50 p-3 text-xs">
          <p className="font-semibold text-navy">{organization?.name || "Workspace"}</p>
          <p className="mt-1 text-slate-500">{organization ? `${organization.plan} · ${organization.status}` : "Loading organization"}</p>
        </div>
        <nav className="mt-6 space-y-1">
          {visible.map((item) => {
            const Icon = item.icon;
            const active = pathname === item.href;
            return (
              <Link key={item.href} href={item.href} className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium ${active ? "bg-blush text-accent" : "text-ink hover:bg-slate-50"}`}>
                <Icon className="size-4" /> {item.label}
              </Link>
            );
          })}
        </nav>
      </aside>
      <main className="lg:pl-64">
        <header className="sticky top-0 z-10 flex h-16 items-center justify-between border-b border-slate-200 bg-white/90 px-4 backdrop-blur lg:px-8">
          <Link href="/dashboard" className="font-semibold lg:hidden">JourneySync AI</Link>
          <div className="hidden text-sm text-slate-600 lg:block">AI suggestions require human verification before sending.</div>
          <div className="flex items-center gap-3 text-sm">
            <SystemStatusPopover />
            <span>{organization?.name ? `${organization.name} / ` : ""}{user?.name || "Demo user"}</span>
            <button aria-label="Log out" className="rounded-md border border-slate-200 p-2" onClick={() => { localStorage.clear(); router.push("/login"); }}><LogOut className="size-4" /></button>
          </div>
        </header>
        <div className="p-4 lg:p-8">{children}</div>
      </main>
    </div>
  );
}

export function PageTitle({ title, subtitle }: { title: string; subtitle: string }) {
  return <div className="mb-6"><h1 className="text-2xl font-bold text-navy">{title}</h1><p className="mt-1 text-sm text-slate-600">{subtitle}</p></div>;
}

"use client";

import { AppShell, PageTitle } from "@/components/app-shell";
import { Badge, Card, Input, Select } from "@/components/ui";
import { api } from "@/lib/api";
import { useRealtime } from "@/lib/ws";
import { Mail, MessageSquare, Smartphone, Store } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

const iconMap: Record<string, any> = { email: Mail, web_chat: MessageSquare, mobile_app: Smartphone, in_store: Store, social: MessageSquare };

export default function InboxPage() {
  const [rows, setRows] = useState<any[]>([]);
  const [filters, setFilters] = useState({ q: "", channel: "", sentiment: "", priority: "" });

  // ── Initial data load (REST) ────────────────────────────────────────────────
  useEffect(() => {
    api<any[]>("/conversations").then(setRows).catch(() => undefined);
  }, []);

  // ── Real-time updates (WebSocket) ───────────────────────────────────────────
  // Replaces the previous setInterval polling loop.
  // Each event updates only the affected conversation row – no full reload.
  useRealtime({
    "conversation.created": (data) => {
      const conv = data as any;
      setRows((prev) =>
        prev.some((r) => r.id === conv.id) ? prev : [conv, ...prev]
      );
    },
    "conversation.updated": (data) => {
      const conv = data as any;
      setRows((prev) =>
        prev.some((r) => r.id === conv.id)
          ? prev.map((r) => (r.id === conv.id ? { ...r, ...conv } : r))
          : [conv, ...prev]  // also handles late-arriving creates
      );
    },
    "conversation.deleted": (data) => {
      const conv = data as any;
      setRows((prev) => prev.filter((r) => r.id !== conv.id));
    },
  });

  const filtered = useMemo(() => rows.filter((row) =>
    (!filters.q || `${row.subject} ${row.customer.name}`.toLowerCase().includes(filters.q.toLowerCase())) &&
    (!filters.channel || row.channel.name === filters.channel) &&
    (!filters.sentiment || row.sentiment === filters.sentiment) &&
    (!filters.priority || row.priority === filters.priority)
  ), [rows, filters]);

  return (
    <AppShell>
      <PageTitle title="Unified Inbox" subtitle="Search, filter, and sort conversations across simulated channels." />
      <Card className="mb-5 grid gap-3 p-4 md:grid-cols-4">
        <Input placeholder="Search customer or subject" value={filters.q} onChange={(e) => setFilters({ ...filters, q: e.target.value })} />
        <Select value={filters.channel} onChange={(e) => setFilters({ ...filters, channel: e.target.value })}><option value="">All channels</option><option value="web_chat">Web chat</option><option value="email">Email</option><option value="mobile_app">Mobile app</option><option value="social">Social</option><option value="in_store">In-store</option></Select>
        <Select value={filters.sentiment} onChange={(e) => setFilters({ ...filters, sentiment: e.target.value })}><option value="">All sentiment</option><option>negative</option><option>neutral</option><option>positive</option></Select>
        <Select value={filters.priority} onChange={(e) => setFilters({ ...filters, priority: e.target.value })}><option value="">All priority</option><option>high</option><option>medium</option><option>low</option></Select>
      </Card>
      <div className="space-y-3">
        {filtered.map((row) => {
          const Icon = iconMap[row.channel.name] || MessageSquare;
          return (
            <Link href={`/workspace?conversation=${row.id}`} key={row.id}>
              <Card className="mb-3 flex items-center gap-4 p-4 transition hover:border-accent/40">
                <Icon className="size-5 text-accent" />
                <div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><b>{row.subject}</b>{row.unread && <Badge>Unread</Badge>}{row.sla_risk && <Badge className="bg-red-50 text-red-700">SLA risk</Badge>}</div><p className="truncate text-sm text-slate-600">{row.customer.name} · {row.latest_message}</p></div>
                <Badge>{row.priority}</Badge><Badge className="bg-slate-100 text-ink">{row.sentiment}</Badge>
              </Card>
            </Link>
          );
        })}
        {!filtered.length && <Card className="p-8 text-center text-slate-500">No conversations match these filters.</Card>}
      </div>
    </AppShell>
  );
}

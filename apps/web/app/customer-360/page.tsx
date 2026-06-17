"use client";

import { AppShell, PageTitle } from "@/components/app-shell";
import { Badge, Card, Select } from "@/components/ui";
import { api } from "@/lib/api";
import { useEffect, useState } from "react";

export default function Customer360Page() {
  const [customers, setCustomers] = useState<any[]>([]);
  const [timeline, setTimeline] = useState<any>(null);
  async function choose(id: string) { setTimeline(await api(`/customers/${id}/timeline`)); }
  useEffect(() => { api<any[]>("/customers").then((rows) => { setCustomers(rows); if (rows[0]) choose(rows[0].id); }); }, []);
  const c = timeline?.customer;
  return <AppShell><PageTitle title="Customer 360" subtitle="Value, preferences, tickets, sentiment, and chronological omnichannel interactions." />
    <Select className="mb-4 max-w-sm" onChange={(e) => choose(e.target.value)}>{customers.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</Select>
    {c && <div className="grid gap-5 lg:grid-cols-[330px_1fr]"><Card className="p-5"><h2 className="text-xl font-bold">{c.name}</h2><p className="text-sm text-slate-600">{c.email}</p><div className="mt-4 flex flex-wrap gap-2"><Badge>{c.loyalty_tier}</Badge><Badge>${c.lifetime_value}</Badge><Badge>{c.preferred_channel}</Badge></div><p className="mt-4 text-sm">Location: {c.location}</p><p className="mt-2 text-sm">Recent purchases: {c.recent_purchases.join(", ")}</p><p className="mt-2 text-sm">CSAT: {c.satisfaction_score} · Churn risk: {Math.round(c.churn_risk_score * 100)}%</p></Card><Card className="p-5"><h2 className="font-semibold">Timeline</h2><div className="mt-4 space-y-4">{timeline.events.map((e: any) => <div key={e.id} className="border-l-2 border-accent pl-4"><b>{e.subject}</b><p className="text-sm">{e.body}</p><small className="text-slate-500">{e.channel_name} · {e.sentiment} · {new Date(e.created_at).toLocaleString()}</small></div>)}</div></Card></div>}
  </AppShell>;
}

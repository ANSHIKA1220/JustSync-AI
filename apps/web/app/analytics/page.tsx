"use client";

import { AppShell, PageTitle } from "@/components/app-shell";
import { Badge, Card, EmptyState, ErrorState, Loading, StatusBadge } from "@/components/ui";
import { api } from "@/lib/api";
import { Activity, Clock, MessageCircleReply, Repeat2, Route, TimerReset } from "lucide-react";
import { useEffect, useState } from "react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

const channelLabel: Record<string, string> = {
  web_chat: "Web chat",
  email: "Email",
  mobile_app: "Mobile app",
  social: "Social DM",
  in_store: "In-store",
};

export default function AnalyticsPage() {
  const [data, setData] = useState<Record<string, any> | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<Record<string, any>>("/analytics/summary").then(setData).catch((err) => setError(err instanceof Error ? err.message : "Could not load analytics."));
  }, []);

  return (
    <AppShell>
      <PageTitle title="Analytics" subtitle="Seeded demo metrics calculated from tenant-scoped conversations, tickets, sentiment, and AI decisions." />
      {error && <ErrorState message={error} />}
      {!data && !error ? <Loading /> : data ? <>
        <div className="grid gap-4 md:grid-cols-3 xl:grid-cols-6">
          {[
            ["First response", `${data.avg_first_response_time}m`, "Median target: under 15m", Clock, "green"],
            ["Avg resolution", `${data.avg_resolution_time}m`, "Coherent across demo tickets", TimerReset, "green"],
            ["Escalation rate", `${data.escalation_rate}%`, "Driven by urgency and churn", Route, "amber"],
            ["Repeat contact", `${data.repeat_contact_rate}%`, "Demo retention signal", Repeat2, "amber"],
            ["AI acceptance", `${data.ai_acceptance_rate}%`, "Human-reviewed replies", MessageCircleReply, "green"],
            ["SLA compliance", `${data.sla_compliance}%`, "SLA risk visible in inbox", Activity, "green"],
          ].map(([label, value, note, Icon, tone]: any) => (
            <Card key={label} className="p-4">
              <Icon className="mb-3 size-5 text-accent" />
              <p className="text-sm text-slate-500">{label}</p>
              <p className="mt-1 text-2xl font-bold text-navy">{value}</p>
              <p className="mt-2 text-xs text-slate-500">{note}</p>
              <div className="mt-3"><StatusBadge tone={tone}>demo metric</StatusBadge></div>
            </Card>
          ))}
        </div>
        <div className="mt-5 grid gap-5 lg:grid-cols-2">
          <Card className="p-4">
            <div className="mb-3 flex items-center justify-between gap-3"><h2 className="font-semibold">Sentiment Trend</h2><Badge>7-day seeded trend</Badge></div>
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={data.sentiment_trend}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Area name="Positive" dataKey="positive" stroke="#14b8a6" fill="#ccfbf1" />
                <Area name="Neutral" dataKey="neutral" stroke="#64748b" fill="#e2e8f0" />
                <Area name="Negative" dataKey="negative" stroke="#d92f8a" fill="#fff1f8" />
              </AreaChart>
            </ResponsiveContainer>
          </Card>
          <Card className="p-4">
            <div className="mb-3 flex items-center justify-between gap-3"><h2 className="font-semibold">Channel Performance</h2><Badge>{data.channel_distribution.length} channels</Badge></div>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={data.channel_distribution.map((item: any) => ({ ...item, name: channelLabel[item.name] || item.name }))}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Bar name="Tickets" dataKey="value" fill="#0f1f3d" />
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </div>
        <div className="mt-5 grid gap-5 lg:grid-cols-3">
          <Card className="p-4">
            <h2 className="font-semibold">Ticket Status Distribution</h2>
            <div className="mt-3 space-y-3">{(data.ticket_status_distribution || []).map((item: any) => <div key={item.name} className="flex items-center justify-between rounded-md bg-slate-50 p-3"><span className="capitalize">{item.name}</span><Badge>{item.value} tickets</Badge></div>)}</div>
          </Card>
          <Card className="p-4">
            <h2 className="font-semibold">High-Risk Segments</h2>
            <div className="mt-3 space-y-3">{data.high_risk_customers.map((customer: any) => <div key={customer.id} className="flex items-center justify-between rounded-md bg-slate-50 p-3"><span><b>{customer.name}</b><small className="block text-slate-500">{customer.tier} / repeat-contact watchlist</small></span><Badge>{Math.round(customer.risk * 100)}% risk</Badge></div>)}</div>
          </Card>
          <Card className="p-4">
            <h2 className="font-semibold">Escalation Queue</h2>
            <div className="mt-3 space-y-3">{data.recent_escalations.map((ticket: any) => <div key={ticket.id} className="rounded-md bg-slate-50 p-3"><div className="flex items-center justify-between gap-2"><b>{ticket.title}</b><StatusBadge tone="amber">{ticket.priority}</StatusBadge></div><p className="mt-1 text-sm text-slate-500">{ticket.department}</p></div>)}</div>
          </Card>
        </div>
      </> : <EmptyState title="No analytics yet" description="Seed demo conversations or create simulated tickets to populate the analytics page." />}
    </AppShell>
  );
}

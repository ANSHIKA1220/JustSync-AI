"use client";

import { AppShell, PageTitle } from "@/components/app-shell";
import { Badge, Button, Card, Skeleton, StatusBadge } from "@/components/ui";
import { api } from "@/lib/api";
import { Activity, Clock, MessageCircle, Play, Sparkles, TicketCheck, TrendingDown, TrendingUp } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type Summary = Record<string, any>;
const colors = ["#d92f8a", "#0f1f3d", "#64748b", "#14b8a6", "#f59e0b"];

export default function DashboardPage() {
  const [data, setData] = useState<Summary | null>(null);
  const [range, setRange] = useState("30 days");
  const router = useRouter();
  useEffect(() => { api<Summary>("/analytics/summary").then(setData); }, []);
  async function runDemo() {
    await api("/demo/run-scenario", { method: "POST", body: "{}" });
    router.push("/workspace");
  }
  return (
    <AppShell>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <PageTitle title="Executive Dashboard" subtitle="Calculated CX health from conversations, tickets, sentiment, and AI decisions." />
        <div className="flex flex-wrap gap-2"><div className="rounded-md border border-slate-200 bg-white p-1">{["7 days", "30 days", "90 days"].map((item) => <button key={item} onClick={() => setRange(item)} className={`rounded px-3 py-1.5 text-sm ${range === item ? "bg-navy text-white" : "text-slate-600"}`}>{item}</button>)}</div><Button onClick={runDemo}><Play className="size-4" /> Run Guided Demo</Button></div>
      </div>
      {!data ? <div className="grid gap-4 md:grid-cols-4">{Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-28" />)}</div> : <>
        <div className="grid gap-4 md:grid-cols-4">
          {[
            ["Active conversations", data.active_conversations, "+2 today", true, MessageCircle, "/inbox"],
            ["Open tickets", data.open_tickets, "-12% vs last week", false, TicketCheck, "/inbox"],
            ["Avg first response", `${data.avg_first_response_time}m`, "1.8m faster", false, Clock, "/analytics"],
            ["AI acceptance", `${data.ai_acceptance_rate}%`, "+5.2%", true, Sparkles, "/audit"],
            ["CSAT", data.customer_satisfaction, "+3.1 pts", true, Activity, "/customer-360"],
            ["Escalation rate", `${data.escalation_rate}%`, "review queue", false, Activity, "/routing"],
            ["Repeat contact", `${data.repeat_contact_rate}%`, "-4.0%", false, Activity, "/analytics"],
            ["SLA compliance", `${data.sla_compliance}%`, "+6.4%", true, Activity, "/analytics"],
          ].map(([label, value, trend, up, Icon, href]: any) => (
            <button key={label} onClick={() => router.push(href)} className="text-left"><Card className="h-full p-4 transition hover:border-accent/40" title="Calculated from database records."><Icon className="mb-3 size-5 text-accent" /><p className="text-sm text-slate-500">{label}</p><p className="mt-1 text-2xl font-bold">{value}</p><p className={`mt-2 flex items-center gap-1 text-xs ${up ? "text-emerald-700" : "text-slate-600"}`}>{up ? <TrendingUp className="size-3" /> : <TrendingDown className="size-3" />}{trend}</p></Card></button>
          ))}
        </div>
        <div className="mt-5 grid gap-5 lg:grid-cols-3">
          <Card className="p-4"><h2 className="font-semibold">Channel Distribution</h2><ResponsiveContainer width="100%" height={250}><PieChart><Pie data={data.channel_distribution} dataKey="value" nameKey="name">{data.channel_distribution.map((_: any, i: number) => <Cell key={i} fill={colors[i % colors.length]} />)}</Pie><Tooltip /><Legend /></PieChart></ResponsiveContainer></Card>
          <Card className="p-4"><h2 className="font-semibold">Sentiment Trend</h2><ResponsiveContainer width="100%" height={250}><AreaChart data={data.sentiment_trend}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="name" /><YAxis /><Tooltip /><Legend /><Area name="Positive sentiment" dataKey="positive" stroke="#14b8a6" fill="#ccfbf1" /><Area name="Neutral sentiment" dataKey="neutral" stroke="#64748b" fill="#e2e8f0" /><Area name="Negative sentiment" dataKey="negative" stroke="#d92f8a" fill="#fff1f8" /></AreaChart></ResponsiveContainer></Card>
          <Card className="p-4"><h2 className="font-semibold">Ticket Volume</h2><ResponsiveContainer width="100%" height={250}><BarChart data={data.ticket_volume}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="name" /><YAxis /><Tooltip /><Legend /><Bar name="Created tickets" dataKey="tickets" fill="#0f1f3d" /><Bar name="Resolved tickets" dataKey="resolved" fill="#d92f8a" /></BarChart></ResponsiveContainer></Card>
        </div>
        <div className="mt-5 grid gap-5 lg:grid-cols-2">
          <Card className="p-4"><h2 className="font-semibold">Recent High-Risk Customers</h2><div className="mt-3 space-y-3">{data.high_risk_customers.map((c: any) => <button key={c.id} onClick={() => router.push("/customer-360")} className="flex w-full items-center justify-between rounded-md bg-slate-50 p-3 text-left hover:bg-blush"><span className="flex items-center gap-3"><span className="flex size-9 items-center justify-center rounded-md bg-navy text-sm font-bold text-white">{c.name.split(" ").map((n: string) => n[0]).join("")}</span><span>{c.name}<small className="block text-slate-500">{c.tier} · repeat contact risk</small></span></span><Badge>{Math.round(c.risk * 100)}% risk</Badge></button>)}</div></Card>
          <Card className="p-4"><h2 className="font-semibold">Recently Escalated Cases</h2><div className="mt-3 space-y-3">{data.recent_escalations.map((t: any) => <button key={t.id} onClick={() => router.push("/workspace")} className="w-full rounded-md bg-slate-50 p-3 text-left hover:bg-blush"><div className="flex items-center justify-between"><b>{t.title}</b><StatusBadge tone="amber">{t.priority}</StatusBadge></div><p className="text-sm text-slate-500">{t.department} · escalation reason: urgency and customer value</p><p className="mt-1 text-xs text-slate-400">Assigned to Sam Support · recently updated</p></button>)}</div></Card>
        </div>
      </>}
    </AppShell>
  );
}

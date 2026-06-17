"use client";

import { AppShell, PageTitle } from "@/components/app-shell";
import { AIProviderBadge } from "@/components/provider-status";
import { Badge, Card, EmptyState, Select, StatusBadge } from "@/components/ui";
import { api } from "@/lib/api";
import { ShieldCheck } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

export default function AuditPage() {
  const [rows, setRows] = useState<any[]>([]);
  const [provider, setProvider] = useState("");
  const [decision, setDecision] = useState("");
  const [openId, setOpenId] = useState<string | null>(null);
  useEffect(() => { api<any[]>("/audit").then(setRows); }, []);
  const filtered = useMemo(() => rows.filter((row) => (!provider || row.model_provider === provider) && (!decision || row.human_decision === decision)), [rows, provider, decision]);
  return <AppShell><div className="mb-6 flex flex-wrap items-start justify-between gap-3"><PageTitle title="Audit and AI Transparency" subtitle="Responsible-AI traceability for provider, sources, confidence, and human decisions." /><AIProviderBadge /></div>
    <Card className="mb-5 p-4"><div className="flex gap-3 text-sm"><ShieldCheck className="size-5 text-accent" /><p>JourneySync never sends AI responses automatically from the agent workspace. Suggestions require human review, and approvals, edits, rejections, retrieved sources, provider, and confidence are logged.</p></div></Card>
    <Card className="mb-5 grid gap-3 p-4 md:grid-cols-3"><Select value={provider} onChange={(e) => setProvider(e.target.value)} aria-label="Provider filter"><option value="">All providers</option><option value="mock">Mock</option><option value="ollama">Ollama</option><option value="openai">OpenAI-compatible</option></Select><Select value={decision} onChange={(e) => setDecision(e.target.value)} aria-label="Decision filter"><option value="">All decisions</option><option value="approved">Approved</option><option value="approved_edited">Edited and approved</option><option value="rejected">Rejected</option><option value="pending">Pending</option><option value="system">System</option></Select><Select aria-label="Date range"><option>All dates</option><option>Last 7 days</option><option>Last 30 days</option></Select></Card>
    <div className="space-y-3">{!filtered.length && <EmptyState title="No matching audit events" description="Adjust filters or run the guided demo to create new AI events." />}{filtered.map((row) => <Card key={row.id} className="p-4"><button className="w-full text-left" onClick={() => setOpenId(openId === row.id ? null : row.id)}><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="font-semibold">{row.action}</h2><div className="flex flex-wrap gap-2"><Badge>{row.model_provider}</Badge><StatusBadge tone={row.model_provider === "mock" && row.action.includes("ai") ? "amber" : "green"}>{row.model_provider === "mock" ? "fallback/mock" : "active"}</StatusBadge><Badge>{Math.round(row.confidence * 100)}%</Badge><Badge>{row.human_decision}</Badge></div></div><p className="mt-2 text-sm text-slate-600">{row.explanation}</p><p className="mt-2 text-xs text-slate-500">{new Date(row.created_at).toLocaleString()}</p></button>{openId === row.id && <div className="mt-4 rounded-md bg-slate-50 p-3 text-sm"><div className="grid gap-3 md:grid-cols-2"><p><b>Provider:</b> {row.model_provider}</p><p><b>Confidence:</b> {Math.round(row.confidence * 100)}%</p><p><b>Agent action:</b> {row.human_decision}</p><p><b>Fallback state:</b> {row.model_provider === "mock" ? "Mock or fallback used" : "Configured provider active"}</p></div>{row.retrieved_sources?.length > 0 && <div className="mt-3"><b>Retrieved sources</b><ul className="mt-1 list-inside list-disc text-slate-600">{row.retrieved_sources.map((s: any) => <li key={s.chunk_id || s.title}>{s.title} · relevance {s.score}</li>)}</ul></div>}</div>}</Card>)}</div>
  </AppShell>;
}

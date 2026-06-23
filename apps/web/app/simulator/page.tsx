"use client";

import { AppShell, PageTitle } from "@/components/app-shell";
import { AIProviderBadge } from "@/components/provider-status";
import { Badge, Button, Card, ConfidenceMeter, EmptyState, Select, StatusBadge, Textarea, Toast } from "@/components/ui";
import { api } from "@/lib/api";
import { Mail, MessageSquare, Send, Smartphone, Store } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

const samples = ["My order arrived damaged.", "I was charged twice.", "I want to cancel my subscription.", "I cannot access my account."];
const channels: Record<string, any> = { web_chat: MessageSquare, email: Mail, mobile_app: Smartphone, social: MessageSquare, in_store: Store };

export default function SimulatorPage() {
  const [customers, setCustomers] = useState<any[]>([]);
  const [customerId, setCustomerId] = useState("");
  const [channel, setChannel] = useState("web_chat");
  const [previousChannel, setPreviousChannel] = useState("web_chat");
  const [body, setBody] = useState("My order arrived damaged after being delayed. I need urgent help.");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [events, setEvents] = useState<any[]>([]);
  const [timeline, setTimeline] = useState<any[]>([]);
  const [analysis, setAnalysis] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState("");
  const customer = useMemo(() => customers.find((c) => c.id === customerId), [customers, customerId]);
  const ChannelIcon = channels[channel] || MessageSquare;

  useEffect(() => {
    api<any[]>("/customers").then((rows) => {
      setCustomers(rows);
      setCustomerId(rows[0]?.id || "");
    });
  }, []);

  useEffect(() => {
    if (!customerId) return;
    api<any>(`/customers/${customerId}/timeline`).then((data) => setTimeline(data.events.slice(-5)));
  }, [customerId]);

  async function send() {
    if (!body.trim() || !customerId) return;
    const outgoing = { sender: "customer", body: body.trim(), channel, time: new Date().toLocaleTimeString() };
    const divider = previousChannel !== channel ? [{ type: "divider", body: `Customer continued this conversation through ${channel.replace("_", " ")}` }] : [];
    setEvents((prev) => [...prev, ...divider, outgoing]);
    setPreviousChannel(channel);
    setBody("");
    setLoading(true);
    setToast("");
    try {
      const result = await api<any>("/messages", { method: "POST", body: JSON.stringify({ customer_id: customerId, conversation_id: conversationId, channel, body: outgoing.body, sender_type: "customer" }) });
      setConversationId(result.conversation_id);
      setAnalysis(result.analysis);
      setEvents((prev) => [...prev, { sender: "ai", body: result.analysis.suggested_response, channel: "JourneySync AI", time: new Date().toLocaleTimeString(), analysis: result.analysis }]);
      setToast("Interaction analyzed and added to the customer journey.");
    } catch {
      setToast("Could not send the simulated interaction. Check that the API is running.");
    } finally {
      setLoading(false);
    }
  }

  return <AppShell><PageTitle title="Customer Chat Simulator" subtitle="Switch simulated channels while preserving customer context." />
    {toast && <Toast message={toast} tone={toast.startsWith("Could") ? "error" : "success"} />}
    <div className="grid gap-5 xl:grid-cols-[340px_1fr_360px]">
      <Card className="p-4">
        <label className="text-sm font-medium">Seeded customer</label>
        <Select className="mt-2" value={customerId} onChange={(e) => { setCustomerId(e.target.value); setConversationId(null); setEvents([]); setAnalysis(null); }} aria-label="Seeded customer">{customers.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</Select>
        <label className="mt-4 block text-sm font-medium">Channel</label>
        <Select className="mt-2" value={channel} onChange={(e) => setChannel(e.target.value)} aria-label="Channel"><option value="web_chat">Web chat</option><option value="email">Email</option><option value="mobile_app">Mobile app</option><option value="social">Social</option><option value="in_store">In-store support</option></Select>
        {customer && <div className="mt-5 rounded-md bg-slate-50 p-3 text-sm"><b>{customer.name}</b><p className="text-slate-500">{customer.loyalty_tier} · {customer.location}</p><p className="mt-2">CSAT {customer.satisfaction_score} · {Math.round(customer.churn_risk_score * 100)}% churn risk</p></div>}
        <h2 className="mt-5 font-semibold">Previous channel interactions</h2>
        <div className="mt-2 space-y-2">{timeline.map((event) => <div key={event.id} className="rounded-md bg-white p-2 text-xs ring-1 ring-slate-200"><b>{event.channel_name}</b><p className="line-clamp-2 text-slate-500">{event.body}</p></div>)}</div>
        <div className="mt-5"><AIProviderBadge /></div>
      </Card>
      <Card className="flex min-h-[620px] flex-col overflow-hidden">
        <div className="flex items-center justify-between border-b border-slate-200 p-4"><div className="flex items-center gap-3"><span className="flex size-10 items-center justify-center rounded-md bg-navy text-white"><ChannelIcon className="size-5" /></span><div><h2 className="font-semibold">{customer?.name || "Customer"}</h2><p className="text-xs text-slate-500">{channel.replace("_", " ")} · online</p></div></div><StatusBadge>Connected</StatusBadge></div>
        <div className="flex-1 space-y-3 overflow-auto bg-slate-50 p-4">
          {!events.length && <EmptyState title="No interactions yet" description="Send a message to begin this customer journey." />}
          {events.map((event, i) => event.type === "divider" ? <div key={i} className="text-center text-xs font-semibold text-accent">{event.body}</div> : <div key={i} className={`rounded-lg p-3 ${event.sender === "customer" ? "mr-10 bg-white" : "ml-10 bg-navy text-white"}`}><div className="mb-1 flex gap-2"><Badge>{event.channel}</Badge>{event.analysis && <Badge>{event.analysis.intent}</Badge>}</div><p className="text-sm">{event.body}</p><small className="mt-1 block opacity-70">{event.time}</small></div>)}
          {loading && <div className="ml-10 rounded-lg bg-navy p-3 text-sm text-white"><span className="inline-flex animate-pulse">JourneySync AI is analyzing intent, retrieving knowledge, and generating a response...</span></div>}
        </div>
        <div className="border-t border-slate-200 bg-white p-4">
          <div className="mb-3 flex flex-wrap gap-2">{samples.map((sample) => <button key={sample} className="rounded-full bg-blush px-3 py-1 text-xs font-semibold text-accent" onClick={() => setBody(sample)}>{sample}</button>)}</div>
          <div className="flex gap-2"><Textarea aria-label="Simulator message" className="min-h-20" value={body} onChange={(e) => setBody(e.target.value)} /><Button onClick={send} disabled={loading || !body.trim()}><Send className="size-4" /> {loading ? "Analyzing" : "Send"}</Button></div>
        </div>
      </Card>
      <Card className="p-4">
        <h2 className="font-semibold">Latest Analysis</h2>
        {!analysis ? <p className="mt-3 text-sm text-slate-500">Analysis appears after the first simulated message.</p> : <div className="mt-4 space-y-3 text-sm"><div className="grid grid-cols-2 gap-2"><Badge>{analysis.intent}</Badge><Badge>{analysis.sentiment}</Badge><Badge>{analysis.urgency}</Badge><Badge>{analysis.recommended_department}</Badge></div><ConfidenceMeter value={analysis.confidence} /><p className="rounded-md bg-amber-50 p-3 text-amber-900">{analysis.next_best_action}</p><h3 className="font-semibold">Knowledge sources</h3>{analysis.sources?.length ? analysis.sources.map((s: any) => <div key={s.chunk_id} className="rounded-md bg-slate-50 p-2"><b>{s.title}</b><p className="text-xs text-slate-500">Relevance {s.score}</p></div>) : <p className="text-slate-500">No retrieved sources for this message.</p>}</div>}
      </Card>
    </div>
  </AppShell>;
}

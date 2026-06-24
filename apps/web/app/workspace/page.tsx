"use client";

import { AppShell, PageTitle } from "@/components/app-shell";
import { AIProviderBadge } from "@/components/provider-status";
import { Badge, Button, Card, ConfidenceMeter, EmptyState, ErrorState, Loading, Select, StatusBadge, Textarea, Toast } from "@/components/ui";
import { api } from "@/lib/api";
import { Check, Clipboard, GitBranch, Loader2, RefreshCw, Send, ShieldAlert, Sparkles, Wand2, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

const channelLabels: Record<string, string> = {
  web_chat: "Web chat",
  email: "Email",
  mobile_app: "Mobile app",
  social: "Social DM",
  in_store: "In-store desk",
  agent_console: "Agent console",
};

const teams = ["Billing", "Delivery", "Technical Support", "Account Support", "Escalations"];

export default function WorkspacePage() {
  const [conversations, setConversations] = useState<any[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selected, setSelected] = useState<any>(null);
  const [ticket, setTicket] = useState<any>(null);
  const [timeline, setTimeline] = useState<any[]>([]);
  const [audit, setAudit] = useState<any[]>([]);
  const [draft, setDraft] = useState("");
  const [composer, setComposer] = useState("");
  const [toast, setToast] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [processing, setProcessing] = useState("");
  const [rejectReason, setRejectReason] = useState("");
  const [team, setTeam] = useState(teams[0]);

  const loadConversations = useCallback(async () => {
    const rows = await api<any[]>("/conversations");
    setConversations(rows);
    if (!selectedId && rows.length) {
      const browserParam = typeof window !== "undefined" ? new URLSearchParams(window.location.search).get("conversation") : null;
      setSelectedId(browserParam || rows[0].id);
    }
    return rows;
  }, [selectedId]);

  const loadDetail = useCallback(async (id: string, options: { preserveDraft?: boolean } = {}) => {
    const [detail, ticketRow, timelineRows, auditRows] = await Promise.all([
      api<any>(`/conversations/${id}`),
      api<any>(`/conversations/${id}/ticket`),
      api<any>(`/conversations/${id}/timeline`),
      api<any[]>("/audit"),
    ]);
    setSelected((current: any) => {
      const sameConversation = current?.id === detail.id;
      if (!options.preserveDraft || !sameConversation) setDraft(detail.ai_suggestion?.suggested_response || "");
      return detail;
    });
    setTicket(ticketRow);
    setTeam(ticketRow.department || teams[0]);
    setTimeline(timelineRows.events || []);
    setAudit(auditRows.slice(0, 6));
  }, []);

  const refreshAll = useCallback(async (options: { preserveDraft?: boolean } = {}) => {
    setError("");
    const rows = await loadConversations();
    const id = selectedId || rows[0]?.id;
    if (id) await loadDetail(id, options);
  }, [loadConversations, loadDetail, selectedId]);

  useEffect(() => {
    refreshAll().catch((err) => setError(err instanceof Error ? err.message : "Could not load workspace.")).finally(() => setLoading(false));
  }, [refreshAll]);

  async function selectConversation(id: string) {
    setSelectedId(id);
    setComposer("");
    setToast("");
    if (typeof window !== "undefined") window.history.replaceState(null, "", `/workspace?conversation=${id}`);
    await loadDetail(id);
  }

  async function withAction(message: string, action: () => Promise<unknown>) {
    setSending(true);
    setError("");
    try {
      await action();
      setToast(message);
      if (selected) await loadDetail(selected.id, { preserveDraft: true });
      await loadConversations();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed.");
    } finally {
      setSending(false);
    }
  }

  async function approve() {
    if (!selected) return;
    await withAction("Suggested reply approved, sent, and recorded in the activity timeline.", () =>
      api(`/ai/suggestions/${selected.ai_suggestion.id}/approve`, { method: "POST", body: JSON.stringify({ edited_response: draft }) })
    );
  }

  async function reject() {
    if (!selected) return;
    await withAction(`Suggestion rejected${rejectReason ? `: ${rejectReason}` : "."}`, async () => {
      await api(`/ai/suggestions/${selected.ai_suggestion.id}/reject`, { method: "POST" });
      setRejectReason("");
    });
  }

  async function regenerate() {
    if (!selected) return;
    setProcessing("Analyzing intent, retrieving knowledge, and drafting reply");
    try {
      const next = await api<any>(`/ai/conversations/${selected.id}/suggest`, { method: "POST", body: "{}" });
      setDraft(next.suggested_response);
      setToast("Suggestion regenerated with current provider settings.");
      await loadDetail(selected.id, { preserveDraft: true });
    } finally {
      setProcessing("");
    }
  }

  async function assignTeam() {
    if (!ticket) return;
    await withAction(`Assigned to ${team}.`, () => api(`/tickets/${ticket.id}/assign-team`, { method: "POST", body: JSON.stringify({ department: team }) }));
  }

  async function escalate() {
    if (!ticket) return;
    await withAction("Ticket escalated to priority handling.", () => api(`/tickets/${ticket.id}/escalate`, { method: "POST", body: "{}" }));
  }

  async function markHighPriority() {
    if (!ticket) return;
    await withAction("Ticket marked high priority.", () => api(`/tickets/${ticket.id}/priority-high`, { method: "POST", body: "{}" }));
  }

  async function resolve() {
    if (!ticket) return;
    await withAction("Ticket resolved and audit event recorded.", () => api(`/tickets/${ticket.id}/resolve`, { method: "POST", body: "{}" }));
  }

  async function reopen() {
    if (!ticket) return;
    await withAction("Ticket reopened and audit event recorded.", () => api(`/tickets/${ticket.id}/reopen`, { method: "POST", body: "{}" }));
  }

  async function sendMessage() {
    if (!selected || !composer.trim()) return;
    await withAction("Agent message added to the unified timeline.", async () => {
      await api("/messages", {
        method: "POST",
        body: JSON.stringify({ conversation_id: selected.id, channel: selected.channel.name, body: composer.trim(), sender_type: "agent" }),
      });
      setComposer("");
    });
  }

  async function demo() {
    const result = await api<any>("/demo/run-scenario", { method: "POST", body: "{}" });
    setToast("Guided damaged-delivery scenario created.");
    setSelectedId(result.conversation_id);
    if (typeof window !== "undefined") window.history.replaceState(null, "", `/workspace?conversation=${result.conversation_id}`);
    await loadConversations();
    await loadDetail(result.conversation_id);
  }

  async function loadSampleData() {
    setSending(true);
    setError("");
    try {
      await api("/demo/load-sample-data", { method: "POST", body: "{}" });
      const rows = await loadConversations();
      const firstId = selectedId || rows[0]?.id;
      if (firstId) {
        setSelectedId(firstId);
        await loadDetail(firstId);
      }
      setToast("Fictional sample data loaded for this organization.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load sample data.");
    } finally {
      setSending(false);
    }
  }

  function rewrite(mode: "shorter" | "empathetic" | "formal") {
    if (mode === "shorter") setDraft(draft.split(". ").slice(0, 2).join(". "));
    if (mode === "empathetic") setDraft(`I understand how frustrating this is. ${draft}`);
    if (mode === "formal") setDraft(`Thank you for contacting JourneySync support. ${draft}`);
  }

  const selectedSources = useMemo(() => selected?.ai_suggestion?.sources || [], [selected]);

  return (
    <AppShell>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <PageTitle title="Agent Workspace" subtitle="Judge-ready support flow with unified customer context, AI reasoning, knowledge sources, and audited human actions." />
        <div className="flex flex-wrap gap-2">
          <Button className="bg-white text-ink ring-1 ring-slate-200 hover:bg-slate-50" onClick={loadSampleData}><Sparkles className="size-4" /> Load Sample Data</Button>
          <Button onClick={demo}><RefreshCw className="size-4" /> Run Demo Scenario</Button>
        </div>
      </div>
      {toast && <Toast message={toast} />}
      {error && <ErrorState message={error} onRetry={() => refreshAll({ preserveDraft: true })} />}
      {loading ? <Loading /> : !conversations.length ? <EmptyState title="No conversations yet" description="Load fictional sample data or run the guided scenario to populate this tenant workspace." /> : (
        <div className="grid gap-4 xl:grid-cols-[300px_1fr_390px]">
          <Card className="p-3">
            <h2 className="mb-3 font-semibold">Curated Demo Queue</h2>
            <div className="space-y-2">
              {conversations.map((c) => (
                <button key={c.id} type="button" onClick={() => selectConversation(c.id)} className={`w-full rounded-md p-3 text-left text-sm transition ${selectedId === c.id ? "bg-blush text-accent ring-1 ring-accent/20" : "bg-slate-50 hover:bg-slate-100"}`}>
                  <span className="block font-semibold">{c.subject}</span>
                  <span className="mt-1 block text-xs text-slate-600">{c.customer.name} / {channelLabels[c.channel.name] || c.channel.name}</span>
                  <span className="mt-2 flex flex-wrap gap-2"><Badge>{c.priority}</Badge><Badge className="bg-slate-100 text-ink">{c.sentiment}</Badge>{c.sla_risk && <StatusBadge tone="amber">SLA risk</StatusBadge>}</span>
                </button>
              ))}
            </div>
          </Card>

          <Card className="p-4">
            {!selected ? <Loading /> : <>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h2 className="text-lg font-bold">{selected.subject}</h2>
                  <p className="mt-1 text-sm text-slate-600">{selected.customer.name} / {selected.customer.loyalty_tier} / {selected.customer.location}</p>
                </div>
                <div className="flex flex-wrap gap-2"><Badge>{channelLabels[selected.channel.name] || selected.channel.name}</Badge><StatusBadge tone={ticket?.status === "resolved" ? "green" : "amber"}>{ticket?.status || "open"}</StatusBadge></div>
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-3">
                <div className="rounded-md bg-slate-50 p-3 text-sm"><b>Lifetime value</b><p>${selected.customer.lifetime_value.toLocaleString()}</p></div>
                <div className="rounded-md bg-slate-50 p-3 text-sm"><b>Churn risk</b><p>{Math.round(selected.customer.churn_risk_score * 100)}%</p></div>
                <div className="rounded-md bg-slate-50 p-3 text-sm"><b>Assigned team</b><p>{ticket?.department}</p></div>
              </div>
              <h3 className="mt-5 font-semibold">Unified Customer Timeline</h3>
              <div className="mt-3 max-h-[500px] space-y-3 overflow-auto pr-2">
                {timeline.map((m: any) => (
                  <div key={m.id} className={`rounded-md border p-3 ${m.conversation_id === selected.id ? "border-accent/30 bg-blush/50" : "border-slate-200 bg-white"}`}>
                    <div className="flex flex-wrap items-center justify-between gap-2"><b className="text-sm">{m.subject}</b><Badge className="bg-slate-100 text-ink">{channelLabels[m.channel_name] || m.channel_name}</Badge></div>
                    <p className="mt-2 text-sm">{m.body}</p>
                    <p className="mt-2 text-xs text-slate-500">{m.sender_type} / {new Date(m.created_at).toLocaleString()} / {m.sentiment}</p>
                  </div>
                ))}
              </div>
              <div className="mt-4 flex gap-2"><Textarea aria-label="Message composer" placeholder="Write a visible agent follow-up" value={composer} onChange={(e) => setComposer(e.target.value)} /><Button onClick={sendMessage} disabled={sending || !composer.trim()}><Send className="size-4" /> Send</Button></div>
            </>}
          </Card>

          <Card className="p-4">
            {selected && <>
              <div className="flex items-start justify-between gap-3"><h2 className="font-semibold">AI Assist Panel</h2><AIProviderBadge compact /></div>
              {processing && <p className="mt-3 flex items-center gap-2 rounded-md bg-blush p-2 text-xs text-accent"><Loader2 className="size-3 animate-spin" /> {processing}</p>}
              <div className="mt-4 grid grid-cols-2 gap-2 text-sm">
                <Badge>Intent: {selected.ai_suggestion.intent}</Badge>
                <Badge>Sentiment: {selected.ai_suggestion.sentiment}</Badge>
                <Badge>Urgency: {selected.ai_suggestion.urgency}</Badge>
                <Badge>Repeat: {selected.ai_suggestion.repeat_contact ? "yes" : "no"}</Badge>
                <Badge>Route: {selected.ai_suggestion.recommended_department}</Badge>
                <Badge>{selected.ai_suggestion.fallback_active ? "Fallback active" : selected.ai_suggestion.provider === "gemini" ? "Gemini" : selected.ai_suggestion.provider}</Badge>
              </div>
              <div className="mt-4"><ConfidenceMeter value={selected.ai_suggestion.confidence} /></div>
              {selected.ai_suggestion.repeat_contact && <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900"><b>Repeat-contact signal:</b> {selected.ai_suggestion.repeat_contact_reason}</div>}
              <div className="mt-4 rounded-md bg-slate-50 p-3 text-sm"><b>Customer history</b><p className="mt-1 text-slate-600">{selected.ai_suggestion.customer_history_summary || selected.ai_suggestion.summary}</p></div>
              <div className="mt-3 rounded-md bg-slate-50 p-3 text-sm"><b>Conversation summary</b><p className="mt-1 text-slate-600">{selected.ai_suggestion.conversation_summary || selected.ai_suggestion.summary}</p></div>
              <div className="mt-3 rounded-md bg-slate-50 p-3 text-sm"><b>Why this route?</b><p className="mt-1 text-slate-600">{selected.ai_suggestion.routing_reason || `Recommended ${selected.ai_suggestion.recommended_department}.`}</p></div>
              <div className="mt-3 rounded-md bg-amber-50 p-3 text-sm text-amber-900"><ShieldAlert className="mr-2 inline size-4" /><b>Next-best action:</b> {selected.ai_suggestion.next_best_action}</div>
              <h3 className="mt-5 font-semibold">Suggested Agent Reply</h3>
              <div className="mt-2 flex flex-wrap gap-2">
                <Button className="h-8 bg-white px-2 text-ink ring-1 ring-slate-200 hover:bg-slate-50" onClick={() => navigator.clipboard.writeText(draft)}><Clipboard className="size-3" /> Copy</Button>
                <Button className="h-8 bg-white px-2 text-ink ring-1 ring-slate-200 hover:bg-slate-50" onClick={regenerate}><Wand2 className="size-3" /> Regenerate</Button>
                <button className="rounded-md bg-slate-100 px-3 py-1 text-xs" onClick={() => rewrite("shorter")}>Shorter</button>
                <button className="rounded-md bg-slate-100 px-3 py-1 text-xs" onClick={() => rewrite("empathetic")}>Empathetic</button>
                <button className="rounded-md bg-slate-100 px-3 py-1 text-xs" onClick={() => rewrite("formal")}>Formal</button>
              </div>
              <Textarea className="mt-3 min-h-36 resize-y rounded-md border border-slate-200 bg-white p-3 text-sm" value={draft} onChange={(e) => setDraft(e.target.value)} aria-label="Editable AI suggestion" />
              <div className="mt-3 grid grid-cols-2 gap-2"><Button onClick={approve} disabled={sending}><Check className="size-4" /> Approve</Button><Button className="bg-white text-ink ring-1 ring-slate-200 hover:bg-slate-50" onClick={reject}><X className="size-4" /> Reject</Button></div>
              <Select className="mt-2" value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} aria-label="Reject reason"><option value="">Optional rejection reason</option><option>Incorrect policy</option><option>Tone not appropriate</option><option>Missing customer context</option></Select>
              <h3 className="mt-5 font-semibold">Knowledge Sources</h3>
              <div className="mt-2 space-y-2">{selectedSources.map((s: any) => <div key={s.chunk_id || s.source_id} className="rounded-md bg-slate-50 p-3 text-sm"><b>{s.title}</b><p className="mt-1 text-xs text-slate-600">{s.snippet || s.excerpt}</p><p className="mt-1 text-xs text-slate-500">Used for this recommendation / source {s.source_id || s.chunk_id}</p></div>)}{!selectedSources.length && <EmptyState title="No sources retrieved" description="The answer is using structured conversation context only for this interaction." />}</div>
              <h3 className="mt-5 font-semibold">Visible Ticket Actions</h3>
              <div className="mt-2 grid gap-2">
                <div className="flex gap-2"><Select value={team} onChange={(e) => setTeam(e.target.value)} aria-label="Assign team">{teams.map((item) => <option key={item}>{item}</option>)}</Select><Button onClick={assignTeam} disabled={sending}><GitBranch className="size-4" /> Assign</Button></div>
                <div className="grid grid-cols-2 gap-2"><Button className="bg-white text-ink ring-1 ring-slate-200 hover:bg-slate-50" onClick={markHighPriority} disabled={sending}><ShieldAlert className="size-4" /> High Priority</Button><Button className="bg-white text-ink ring-1 ring-slate-200 hover:bg-slate-50" onClick={escalate} disabled={sending}><Sparkles className="size-4" /> Escalate</Button></div>
                <div className="grid grid-cols-2 gap-2"><Button className="bg-white text-ink ring-1 ring-slate-200 hover:bg-slate-50" onClick={resolve} disabled={sending}><Check className="size-4" /> Resolve</Button><Button className="bg-white text-ink ring-1 ring-slate-200 hover:bg-slate-50" onClick={reopen} disabled={sending}><RefreshCw className="size-4" /> Reopen</Button></div>
              </div>
              <h3 className="mt-5 font-semibold">Activity Timeline</h3>
              <div className="mt-2 space-y-2">{audit.map((row) => <div key={row.id} className="rounded-md border border-slate-200 p-3 text-sm"><div className="flex items-center justify-between gap-2"><b>{row.action.replaceAll("_", " ")}</b><Badge className="bg-slate-100 text-ink">{row.human_decision}</Badge></div><p className="mt-1 text-xs text-slate-600">{row.explanation}</p><p className="mt-1 text-xs text-slate-400">{new Date(row.created_at).toLocaleString()}</p></div>)}</div>
            </>}
          </Card>
        </div>
      )}
    </AppShell>
  );
}

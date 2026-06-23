"use client";

import { AppShell, PageTitle } from "@/components/app-shell";
import { AIProviderBadge } from "@/components/provider-status";
import { Badge, Button, Card, ConfidenceMeter, Select, StatusBadge, Textarea, Toast } from "@/components/ui";
import { api } from "@/lib/api";
import { useRealtime } from "@/lib/ws";
import { Check, Clipboard, RefreshCw, Send, ShieldAlert, Wand2, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

export default function WorkspacePage() {
  const [conversations, setConversations] = useState<any[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selected, setSelected] = useState<any>(null);
  const [draft, setDraft] = useState("");
  const [composer, setComposer] = useState("");
  const [toast, setToast] = useState("");
  const [sending, setSending] = useState(false);
  const [processing, setProcessing] = useState("");
  const [rejectReason, setRejectReason] = useState("");

  // Track whether the user has manually edited the AI draft so WebSocket
  // updates don't silently overwrite unsaved edits.
  const draftModifiedRef = useRef(false);

  // Keep selectedId accessible inside WS event closures without stale captures.
  const selectedIdRef = useRef<string | null>(null);
  selectedIdRef.current = selectedId;

  // ── Initial data loads (REST) ───────────────────────────────────────────────
  const loadConversations = useCallback(async () => {
    const rows = await api<any[]>("/conversations");
    setConversations(rows);
    if (!selectedIdRef.current && rows.length) {
      const param =
        typeof window !== "undefined"
          ? new URLSearchParams(window.location.search).get("conversation")
          : null;
      setSelectedId(param || rows[0].id);
    }
  }, []);

  const loadDetail = useCallback(
    async (id: string, options: { preserveDraft?: boolean } = {}) => {
      const detail = await api<any>(`/conversations/${id}`);
      setSelected((current: any) => {
        const isSameConversation = current?.id === detail.id;
        if (!options.preserveDraft || !isSameConversation) {
          setDraft(detail.ai_suggestion?.suggested_response || "");
          draftModifiedRef.current = false;
        }
        return detail;
      });
    },
    []
  );

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  useEffect(() => {
    if (!selectedId) return;
    loadDetail(selectedId);
  }, [selectedId, loadDetail]);

  // ── Real-time updates (WebSocket) ───────────────────────────────────────────
  // Replaces two setInterval polling loops (conversations list + detail panel).
  //
  // Design decisions:
  //   • conversation.created – prepend to list; auto-select if nothing is selected.
  //   • conversation.updated – update the list row; merge into detail if selected.
  //     Draft is NOT overwritten if the user has already edited it.
  //   • suggestion.updated  – update just the suggestion sub-object in detail.
  //   • ticket.updated      – no workspace UI surface; silently ignored.
  useRealtime({
    "conversation.created": (data) => {
      const conv = data as any;
      setConversations((prev) =>
        prev.some((c) => c.id === conv.id) ? prev : [conv, ...prev]
      );
      if (!selectedIdRef.current) setSelectedId(conv.id);
    },

    "conversation.updated": (data) => {
      const conv = data as any;

      // 1. Keep the sidebar list row current.
      setConversations((prev) =>
        prev.some((c) => c.id === conv.id)
          ? prev.map((c) => (c.id === conv.id ? { ...c, ...conv } : c))
          : [conv, ...prev]
      );

      // 2. If this is the currently open conversation, merge into the detail panel.
      if (conv.id !== selectedIdRef.current) return;

      setSelected((current: any) => {
        if (!current || current.id !== conv.id) return current;

        // Merge all fields from the event into current state.
        const next = { ...current, ...conv };

        // Only update the draft textarea if the user hasn't typed anything yet.
        // This preserves edits-in-progress across background WS refreshes.
        if (!draftModifiedRef.current && conv.ai_suggestion?.suggested_response) {
          setDraft(conv.ai_suggestion.suggested_response);
        }

        return next;
      });
    },

    "suggestion.updated": (data) => {
      const suggestion = data as any;
      setSelected((current: any) => {
        if (!current || current.ai_suggestion?.id !== suggestion.id) return current;
        const next = { ...current, ai_suggestion: { ...current.ai_suggestion, ...suggestion } };
        // If suggestion was just approved/rejected, the draft no longer needs guarding.
        if (suggestion.status === "approved" || suggestion.status === "rejected") {
          draftModifiedRef.current = false;
        }
        return next;
      });
    },
  });

  // ── User actions ────────────────────────────────────────────────────────────

  async function selectConversation(id: string) {
    setSelectedId(id);
    setComposer("");
    setToast("");
    draftModifiedRef.current = false;
    if (typeof window !== "undefined") {
      window.history.replaceState(null, "", `/workspace?conversation=${id}`);
    }
    await loadDetail(id);
  }

  async function approve() {
    if (!selected) return;
    setSending(true);
    await api(`/ai/suggestions/${selected.ai_suggestion.id}/approve`, {
      method: "POST",
      body: JSON.stringify({ edited_response: draft }),
    });
    setToast("Suggestion approved, sent, and recorded in audit log.");
    draftModifiedRef.current = false;
    await loadDetail(selected.id);
    setSending(false);
  }

  async function reject() {
    if (!selected) return;
    await api(`/ai/suggestions/${selected.ai_suggestion.id}/reject`, { method: "POST" });
    setToast(`Suggestion rejected and recorded${rejectReason ? `: ${rejectReason}` : "."}`);
    setRejectReason("");
    draftModifiedRef.current = false;
    await loadDetail(selected.id);
  }

  async function regenerate() {
    if (!selected) return;
    setProcessing("Analyzing intent → retrieving knowledge → generating response");
    const next = await api<any>(`/ai/conversations/${selected.id}/suggest`, { method: "POST", body: "{}" });
    setDraft(next.suggested_response);
    draftModifiedRef.current = false;
    setToast("Suggestion regenerated with current provider settings.");
    await loadDetail(selected.id);
    setProcessing("");
  }

  function rewrite(mode: "shorter" | "empathetic" | "formal") {
    draftModifiedRef.current = true;
    if (mode === "shorter") setDraft(draft.split(". ").slice(0, 2).join(". "));
    if (mode === "empathetic") setDraft(`I understand how frustrating this is. ${draft}`);
    if (mode === "formal") setDraft(`Thank you for contacting JourneySync AI support. ${draft}`);
  }

  async function copySuggestion() {
    await navigator.clipboard.writeText(draft);
    setToast("Suggestion copied to clipboard.");
  }

  async function demo() {
    const result = await api<any>("/demo/run-scenario", { method: "POST", body: "{}" });
    setToast("Guided damaged-delivery scenario created.");
    setSelectedId(result.conversation_id);
    await loadConversations();
    await loadDetail(result.conversation_id);
  }

  async function sendMessage() {
    if (!selected || !composer.trim()) return;
    setSending(true);
    try {
      await api("/messages", {
        method: "POST",
        body: JSON.stringify({
          conversation_id: selected.id,
          channel: selected.channel.name,
          body: composer.trim(),
          sender_type: "agent",
        }),
      });
      setComposer("");
      setToast("Message sent and conversation timeline updated.");
      await loadDetail(selected.id, { preserveDraft: true });
      await loadConversations();
    } finally {
      setSending(false);
    }
  }

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <AppShell>
      <PageTitle title="Agent Workspace" subtitle="Three-column customer context, complete conversation, and responsible AI controls." />
      {toast && <Toast message={toast} />}
      <div className="mb-4 flex gap-2"><Button onClick={demo}><RefreshCw className="size-4" /> Run Demo Scenario</Button></div>
      <div className="grid gap-4 xl:grid-cols-[290px_1fr_360px]">
        <Card className="p-3">
          <h2 className="mb-3 font-semibold">Priority Conversations</h2>
          {conversations.map((c) => (
            <button key={c.id} type="button" onClick={() => selectConversation(c.id)} className={`mb-2 w-full rounded-md p-3 text-left text-sm ${selectedId === c.id ? "bg-blush text-accent" : "bg-slate-50"}`}>
              <b>{c.subject}</b>
              <span className="block text-xs">{c.customer.name} - {c.priority}</span>
            </button>
          ))}
        </Card>
        <Card className="p-4">
          {!selected ? <p>Loading workspace</p> : <>
            <div className="flex flex-wrap items-center justify-between gap-2"><div><h2 className="text-lg font-bold">{selected.subject}</h2><p className="text-xs text-slate-500">Channel history is preserved across touchpoints.</p></div><div className="flex gap-2"><Badge>{selected.channel.name}</Badge><Badge>{selected.sentiment}</Badge>{selected.sla_risk && <StatusBadge tone="amber">SLA risk</StatusBadge>}</div></div>
            <div className="mt-4 max-h-[520px] space-y-3 overflow-auto pr-2">{selected.messages.map((m: any) => <div key={m.id} className={`rounded-lg p-3 ${m.sender_type === "agent" ? "ml-8 bg-navy text-white" : "mr-8 bg-slate-100"}`}>
              {m.metadata_json?.recipients && <div className="mb-2 border-b border-slate-200 pb-2 text-xs opacity-80">
                <b>Provider:</b> {m.channel_name === "email" ? "Email Integration" : "Standard"}<br />
                <b>To:</b> {m.metadata_json.recipients.join(", ")}
                {m.metadata_json.thread_id && <><br /><b>Thread ID:</b> {m.metadata_json.thread_id}</>}
              </div>}
              <p className="whitespace-pre-wrap text-sm">{m.body}</p>
              {m.attachments?.length > 0 && <div className="mt-3 flex flex-wrap gap-2">{m.attachments.map((a: any) => <Badge key={a.id} className="bg-slate-200 text-slate-800">📎 {a.filename}</Badge>)}</div>}
              <small className="mt-2 block opacity-70">{m.sender_type} - {new Date(m.created_at).toLocaleString()}</small>
            </div>)}</div>
            <div className="mt-4 flex gap-2"><Textarea aria-label="Message composer" placeholder="Write a message" value={composer} onChange={(e) => setComposer(e.target.value)} /><Button onClick={sendMessage} disabled={sending || !composer.trim()}><Send className="size-4" /> {sending ? "Sending" : "Send"}</Button></div>
          </>}
        </Card>
        <Card className="p-4">
          {selected && <><div className="flex items-start justify-between gap-3"><div><h2 className="font-semibold">Customer Profile</h2><p className="mt-2 text-sm">{selected.customer.name}<br />{selected.customer.email}</p></div><AIProviderBadge compact /></div><div className="mt-3 grid grid-cols-2 gap-2 text-sm"><Badge>{selected.customer.loyalty_tier}</Badge><Badge>{Math.round(selected.customer.churn_risk_score * 100)}% churn</Badge></div>
          <h2 className="mt-5 font-semibold">AI analysis</h2>{processing && <p className="mt-2 animate-pulse rounded-md bg-blush p-2 text-xs text-accent">{processing}</p>}<p className="mt-2 text-sm text-slate-600">{selected.ai_suggestion.summary}</p><div className="mt-3 grid grid-cols-2 gap-2 text-sm"><Badge>{selected.ai_suggestion.intent}</Badge><Badge>{selected.ai_suggestion.urgency}</Badge><Badge>{selected.ai_suggestion.recommended_department}</Badge><Badge>{selected.ai_suggestion.provider}</Badge></div><div className="mt-3"><ConfidenceMeter value={selected.ai_suggestion.confidence} /></div>
          <h2 className="mt-5 font-semibold">Suggested response</h2>
          <div className="mt-2 flex flex-wrap gap-2"><Button className="h-8 bg-white px-2 text-ink ring-1 ring-slate-200 hover:bg-slate-50" onClick={copySuggestion}><Clipboard className="size-3" /> Copy</Button><Button className="h-8 bg-white px-2 text-ink ring-1 ring-slate-200 hover:bg-slate-50" onClick={regenerate}><Wand2 className="size-3" /> Regenerate</Button><button className="rounded-full bg-slate-100 px-3 py-1 text-xs" onClick={() => rewrite("shorter")}>Shorter</button><button className="rounded-full bg-slate-100 px-3 py-1 text-xs" onClick={() => rewrite("empathetic")}>More empathetic</button><button className="rounded-full bg-slate-100 px-3 py-1 text-xs" onClick={() => rewrite("formal")}>More formal</button></div>
          <Textarea
            className="mt-4 min-h-36 resize-y"
            value={draft}
            onChange={(e) => { setDraft(e.target.value); draftModifiedRef.current = true; }}
            aria-label="Editable AI suggestion"
          />
          {draft !== selected.ai_suggestion.suggested_response && <div className="mt-3 rounded-md bg-slate-50 p-3 text-xs text-slate-600"><b>Edited response comparison</b><p className="mt-1 line-clamp-2">Original: {selected.ai_suggestion.suggested_response}</p><p className="mt-1 line-clamp-2">Final: {draft}</p></div>}
          <p className="mt-2 text-xs text-slate-500">Human verification required before sending. Retrieved sources are advisory.</p>
          <div className="mt-3 grid gap-2"><div className="flex flex-wrap gap-2"><Button onClick={approve} disabled={sending}><Check className="size-4" /> Approve and Send</Button><Button className="bg-white text-ink ring-1 ring-slate-200 hover:bg-slate-50" onClick={() => setToast("Draft saved locally for this session.")}>Save as Draft</Button><Button className="bg-white text-ink ring-1 ring-slate-200 hover:bg-slate-50" onClick={() => setToast("Case escalated to priority queue.")}>Escalate</Button><Button className="bg-white text-ink ring-1 ring-slate-200 hover:bg-slate-50" onClick={() => setToast("Conversation marked resolved for demo.")}>Resolve</Button></div><Select value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} aria-label="Reject reason"><option value="">Optional rejection reason</option><option>Incorrect policy</option><option>Tone not appropriate</option><option>Missing customer context</option></Select><Button className="bg-white text-ink ring-1 ring-slate-200 hover:bg-slate-50" onClick={reject}><X className="size-4" /> Reject Suggestion</Button></div>
          <h2 className="mt-5 font-semibold">Retrieved Sources</h2><div className="mt-2 space-y-2">{selected.ai_suggestion.sources.map((s: any) => <div key={s.chunk_id} className="rounded-md bg-slate-50 p-2 text-sm"><b>{s.title}</b><p className="text-xs text-slate-500">Relevance {s.score}</p></div>)}</div>
          <div className="mt-4 rounded-md bg-amber-50 p-3 text-sm text-amber-800"><ShieldAlert className="mr-2 inline size-4" /> Next best action: {selected.ai_suggestion.next_best_action}</div></>}
        </Card>
      </div>
    </AppShell>
  );
}

"use client";

import { AppShell, PageTitle } from "@/components/app-shell";
import { Badge, Button, Card, Input, Textarea } from "@/components/ui";
import { api } from "@/lib/api";
import { Search, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

export default function KnowledgePage() {
  const [docs, setDocs] = useState<any[]>([]);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [query, setQuery] = useState("damaged replacement");
  const [results, setResults] = useState<any[]>([]);
  async function load() { setDocs(await api("/knowledge")); }
  useEffect(() => { load(); }, []);
  async function add() { await api("/knowledge", { method: "POST", body: JSON.stringify({ title, content }) }); setTitle(""); setContent(""); await load(); }
  async function search() { setResults(await api(`/knowledge/search?q=${encodeURIComponent(query)}`)); }
  return <AppShell><PageTitle title="Knowledge Base" subtitle="View, add, edit, delete, re-index, and search enterprise knowledge documents." />
    <div className="grid gap-5 lg:grid-cols-[1fr_380px]"><Card className="p-4"><h2 className="font-semibold">Documents</h2><div className="mt-3 space-y-3">{docs.map((d) => <div key={d.id} className="flex items-center justify-between rounded-md bg-slate-50 p-3"><div><b>{d.title}</b><p className="text-sm text-slate-500">{d.status} · {d.chunk_count} chunks</p></div><button aria-label="Delete document" onClick={async () => { await api(`/knowledge/${d.id}`, { method: "DELETE" }); load(); }}><Trash2 className="size-4 text-slate-500" /></button></div>)}</div></Card>
    <div className="space-y-5"><Card className="p-4"><h2 className="font-semibold">Add Document</h2><Input className="mt-3" placeholder="Title" value={title} onChange={(e) => setTitle(e.target.value)} /><Textarea className="mt-3" placeholder="Policy text" value={content} onChange={(e) => setContent(e.target.value)} /><Button className="mt-3" onClick={add}>Add and index</Button></Card><Card className="p-4"><h2 className="font-semibold">Search</h2><div className="mt-3 flex gap-2"><Input value={query} onChange={(e) => setQuery(e.target.value)} /><Button onClick={search}><Search className="size-4" /></Button></div><div className="mt-3 space-y-2">{results.map((r) => <div key={r.chunk_id} className="rounded-md bg-slate-50 p-2 text-sm"><b>{r.title}</b><Badge className="ml-2">{r.score}</Badge><p className="mt-1 text-slate-500">{r.excerpt}</p></div>)}</div></Card></div></div>
  </AppShell>;
}

import { AIProviderBadge } from "@/components/provider-status";
import { Button, Card, StatusBadge } from "@/components/ui";
import { ArrowDown, ArrowRight, BrainCircuit, Building2, Mail, MessageSquareText, ShieldCheck, Smartphone, Store } from "lucide-react";
import Link from "next/link";

const journey = [
  { icon: MessageSquareText, channel: "Web chat", issue: "Delayed delivery", sentiment: "Concerned", time: "Mon 10:14", status: "Linked" },
  { icon: Mail, channel: "Email", issue: "Damaged order", sentiment: "Negative", time: "Tue 09:42", status: "High urgency" },
  { icon: Smartphone, channel: "Mobile", issue: "Replacement update", sentiment: "Recovering", time: "Tue 12:05", status: "Policy found" },
  { icon: Store, channel: "In-store", issue: "Pickup confirmation", sentiment: "Positive", time: "Wed 16:20", status: "Resolved" },
];

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-white text-navy">
      <section className="relative overflow-hidden bg-[linear-gradient(120deg,#ffffff,#f6f8fb)] px-6 py-12 md:px-12">
        <div className="mx-auto grid max-w-7xl items-center gap-10 lg:grid-cols-[0.9fr_1.1fr]">
          <div>
            <div className="mb-4 flex flex-wrap gap-2"><StatusBadge>Local AI ready</StatusBadge><StatusBadge tone="slate">No paid API required</StatusBadge><AIProviderBadge /></div>
            <h1 className="max-w-3xl text-5xl font-bold tracking-normal md:text-7xl">JourneySync AI</h1>
            <p className="mt-6 max-w-2xl text-lg text-slate-600">Unify every customer touchpoint into one timeline, detect urgency and churn risk, retrieve policy context, and help agents send verified responses faster.</p>
            <div className="mt-8 flex flex-wrap gap-3"><Link href="/login"><Button>Launch Demo <ArrowRight className="size-4" /></Button></Link><a href="#architecture"><Button className="bg-white text-ink ring-1 ring-slate-200 hover:bg-slate-50">View Architecture <ArrowDown className="size-4" /></Button></a></div>
          </div>
          <div className="relative">
            <div className="absolute left-8 top-10 hidden h-[calc(100%-80px)] w-px bg-accent/30 md:block" />
            <div className="grid gap-4">
              {journey.map((item, i) => {
                const Icon = item.icon;
                return <Card key={item.channel} className="relative p-5 transition hover:-translate-y-0.5 hover:border-accent/40"><div className="flex items-start gap-4"><span className="z-10 flex size-10 shrink-0 items-center justify-center rounded-md bg-navy text-white"><Icon className="size-5" /></span><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center justify-between gap-2"><b>{item.channel}</b><span className="text-xs text-slate-500">{item.time}</span></div><p className="mt-1 text-sm text-slate-600">{item.issue}</p><div className="mt-3 flex flex-wrap gap-2"><StatusBadge tone={item.sentiment === "Negative" ? "amber" : "green"}>{item.sentiment}</StatusBadge><StatusBadge tone="slate">{item.status}</StatusBadge></div></div></div>{i < journey.length - 1 && <div className="absolute -bottom-3 left-9 hidden size-3 animate-pulse rounded-full bg-accent md:block" />}</Card>;
              })}
            </div>
          </div>
        </div>
      </section>
      <section className="mx-auto max-w-7xl px-6 py-10">
        <Card className="p-5"><b>Demo scenario:</b><span className="ml-2 text-slate-600">Priya starts with a delayed-delivery web chat and later reports a damaged order by email. JourneySync AI links both interactions and recommends a priority replacement.</span></Card>
      </section>
      <section className="mx-auto grid max-w-7xl gap-5 px-6 py-8 md:grid-cols-4">
        {[
          ["Ingest interaction", "Normalize web, email, mobile, social, and in-store messages."],
          ["Understand context", "Unify customer history, value, sentiment, urgency, and risk."],
          ["Retrieve and route", "Find policy sources and recommend the next best department."],
          ["Human reviews", "Agents edit, approve, reject, or send with full auditability."],
        ].map(([title, copy], i) => <Card key={title} className="p-5"><span className="mb-4 flex size-8 items-center justify-center rounded-md bg-blush text-sm font-bold text-accent">{i + 1}</span><h2 className="font-semibold">{title}</h2><p className="mt-2 text-sm text-slate-600">{copy}</p></Card>)}
      </section>
      <section id="architecture" className="mx-auto max-w-7xl px-6 py-12">
        <h2 className="text-2xl font-bold">Solution Architecture</h2>
        <div className="mt-5 grid gap-4 md:grid-cols-4">
          {[["Channels", MessageSquareText], ["FastAPI orchestration", Building2], ["AI + RAG + routing", BrainCircuit], ["Database + analytics", ShieldCheck]].map(([label, Icon]: any) => <Card key={label} className="p-5 text-center"><Icon className="mx-auto mb-3 size-7 text-accent" /><b>{label}</b></Card>)}
        </div>
      </section>
    </main>
  );
}

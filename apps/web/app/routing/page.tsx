"use client";

import { AppShell, PageTitle } from "@/components/app-shell";
import { Badge, Card } from "@/components/ui";
import { api } from "@/lib/api";
import { useEffect, useState } from "react";

export default function RoutingPage() {
  const [rules, setRules] = useState<any[]>([]);
  useEffect(() => { api<any[]>("/routing/rules").then(setRules); }, []);
  return <AppShell><PageTitle title="Routing and Escalation" subtitle="Rules combine AI classification with business constraints while avoiding protected personal attributes." />
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{rules.map((r) => <Card key={r.id} className="p-4"><h2 className="font-semibold">{r.name}</h2><div className="mt-3 flex flex-wrap gap-2">{["intent", "sentiment", "urgency", "channel", "loyalty_tier"].map((k) => r[k] && <Badge key={k}>{k}: {r[k]}</Badge>)}{r.churn_risk_min && <Badge>risk &gt; {r.churn_risk_min}</Badge>}</div><p className="mt-4 text-sm text-slate-600">Department: <b>{r.department}</b></p></Card>)}</div>
  </AppShell>;
}

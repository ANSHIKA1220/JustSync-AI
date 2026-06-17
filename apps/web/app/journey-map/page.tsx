import { AppShell, PageTitle } from "@/components/app-shell";
import { Badge, Card } from "@/components/ui";

const stages = [
  ["Awareness", "Social question", "positive"],
  ["Consideration", "Product recommendation", "neutral"],
  ["Purchase", "Mobile checkout", "positive"],
  ["Delivery", "Delayed shipment", "negative"],
  ["Support", "Damaged product email", "negative"],
  ["Retention", "Priority replacement", "recovering"]
];

export default function JourneyMapPage() {
  return <AppShell><PageTitle title="Customer Journey Map" subtitle="Touchpoints, channels, sentiment, and friction points across the lifecycle." />
    <div className="grid gap-4 md:grid-cols-3 xl:grid-cols-6">{stages.map(([stage, touchpoint, sentiment], i) => <Card key={stage} className="p-4"><div className="mb-4 flex size-10 items-center justify-center rounded-md bg-blush font-bold text-accent">{i + 1}</div><h2 className="font-semibold">{stage}</h2><p className="mt-2 text-sm text-slate-600">{touchpoint}</p><Badge className="mt-4">{sentiment}</Badge>{sentiment === "negative" && <p className="mt-3 rounded-md bg-red-50 p-2 text-xs text-red-700">Friction point requiring proactive outreach.</p>}</Card>)}</div>
  </AppShell>;
}

import { cn } from "@/lib/utils";
import { AlertCircle, CheckCircle2, Info, Loader2 } from "lucide-react";
import type { ButtonHTMLAttributes, HTMLAttributes, InputHTMLAttributes, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";

export function Button({ className, ...props }: ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button className={cn("focus-ring inline-flex h-10 items-center justify-center gap-2 rounded-md bg-accent px-4 text-sm font-semibold text-white shadow-sm transition hover:bg-accent/90 disabled:opacity-60", className)} {...props} />;
}

export function IconButton({ className, ...props }: ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button className={cn("focus-ring inline-flex size-9 items-center justify-center rounded-md border border-slate-200 bg-white text-ink transition hover:border-accent/40 hover:text-accent", className)} {...props} />;
}

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-lg border border-slate-200 bg-white shadow-soft", className)} {...props} />;
}

export function Badge({ className, ...props }: HTMLAttributes<HTMLSpanElement>) {
  return <span className={cn("inline-flex items-center rounded-full bg-blush px-2.5 py-1 text-xs font-semibold text-accent", className)} {...props} />;
}

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input className="focus-ring h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm" {...props} />;
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className="focus-ring h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm" {...props} />;
}

export function Textarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className="focus-ring min-h-28 w-full rounded-md border border-slate-200 bg-white p-3 text-sm" {...props} />;
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-md bg-slate-200", className)} />;
}

export function Loading() {
  return <div className="flex items-center gap-2 text-sm text-slate-500"><Loader2 className="size-4 animate-spin" /> Loading</div>;
}

export function EmptyState({ title, description }: { title: string; description: string }) {
  return <div className="rounded-lg border border-dashed border-slate-300 bg-white p-8 text-center"><Info className="mx-auto mb-3 size-6 text-slate-400" /><h3 className="font-semibold text-navy">{title}</h3><p className="mt-1 text-sm text-slate-500">{description}</p></div>;
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800"><AlertCircle className="mr-2 inline size-4" />{message}{onRetry && <Button className="ml-3 h-8 bg-white text-red-700 ring-1 ring-red-200 hover:bg-red-50" onClick={onRetry}>Retry</Button>}</div>;
}

export function StatusBadge({ tone = "green", children, title }: { tone?: "green" | "amber" | "red" | "slate"; children: React.ReactNode; title?: string }) {
  const colors = {
    green: "bg-emerald-50 text-emerald-700 ring-emerald-200",
    amber: "bg-amber-50 text-amber-800 ring-amber-200",
    red: "bg-red-50 text-red-700 ring-red-200",
    slate: "bg-slate-100 text-slate-700 ring-slate-200",
  };
  const dot = { green: "bg-emerald-500", amber: "bg-amber-500", red: "bg-red-500", slate: "bg-slate-400" };
  return <span title={title} className={cn("inline-flex items-center gap-2 rounded-full px-2.5 py-1 text-xs font-semibold ring-1", colors[tone])}><span className={cn("size-2 rounded-full", dot[tone])} />{children}</span>;
}

export function ConfidenceMeter({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  return <div aria-label={`Confidence ${pct}%`}><div className="flex items-center justify-between text-xs text-slate-500"><span>Confidence</span><span>{pct}%</span></div><div className="mt-1 h-2 rounded-full bg-slate-100"><div className="h-2 rounded-full bg-accent" style={{ width: `${pct}%` }} /></div></div>;
}

export function Toast({ message, tone = "success" }: { message: string; tone?: "success" | "warning" | "error" }) {
  const tones = { success: "bg-emerald-50 text-emerald-800", warning: "bg-amber-50 text-amber-800", error: "bg-red-50 text-red-800" };
  return <div role="status" className={cn("mb-4 flex items-center gap-2 rounded-md p-3 text-sm", tones[tone])}><CheckCircle2 className="size-4" />{message}</div>;
}

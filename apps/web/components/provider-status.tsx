"use client";

import { api, type HealthStatus } from "@/lib/api";
import { useRealtime } from "@/lib/ws";
import { cn } from "@/lib/utils";
import { Activity, Database, RefreshCw, Server } from "lucide-react";
import { useEffect, useState } from "react";
import { Button, Card, StatusBadge } from "./ui";

function providerLabel(status?: HealthStatus | null) {
  if (!status) return "Checking AI";
  if (status.fallback_active) return "Mock fallback active";
  if (status.active_provider === "ollama") return `Ollama · ${status.model}`;
  if (status.active_provider === "openai") return `OpenAI-compatible · ${status.model}`;
  return "Mock AI";
}

export function AIProviderBadge({ compact = false }: { compact?: boolean }) {
  const [status, setStatus] = useState<HealthStatus | null>(null);

  // Initial HTTP fetch for first-paint data (before WS connects).
  useEffect(() => {
    api<HealthStatus>("/health").then(setStatus).catch(() => setStatus(null));
  }, []);

  // Live provider updates via WebSocket – badge refreshes without polling.
  useRealtime({
    "provider.status": (data) => setStatus(data as HealthStatus),
  });

  const tone = status?.fallback_active ? "amber" : status?.status === "healthy" ? "green" : "red";
  return (
    <StatusBadge
      tone={tone}
      title={
        status?.fallback_active
          ? "Configured AI provider is unavailable; deterministic mock fallback is active."
          : "Current AI provider status."
      }
    >
      {compact ? providerLabel(status).replace("OpenAI-compatible", "OpenAI") : providerLabel(status)}
    </StatusBadge>
  );
}

export function SystemStatusPopover() {
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<HealthStatus | null>(null);
  const [checkedAt, setCheckedAt] = useState<string>("");

  async function refresh() {
    const next = await api<HealthStatus>("/health");
    setStatus(next);
    setCheckedAt(new Date().toLocaleTimeString());
  }

  useEffect(() => {
    refresh().catch(() => undefined);
  }, []);

  // Live provider status pushes update the popover without polling.
  useRealtime({
    "provider.status": (data) => {
      setStatus(data as HealthStatus);
      setCheckedAt(new Date().toLocaleTimeString());
    },
  });

  return (
    <div className="relative">
      <button
        aria-label="System status"
        onClick={() => setOpen(!open)}
        className={cn(
          "focus-ring inline-flex h-9 items-center gap-2 rounded-md border border-slate-200 bg-white px-3 text-sm",
          status?.fallback_active && "border-amber-300 bg-amber-50"
        )}
      >
        <Activity className="size-4 text-accent" /> Status
      </button>
      {open && (
        <Card className="absolute right-0 top-11 z-30 w-80 p-4">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold">System Status</h3>
            <Button className="h-8 px-2" onClick={refresh}><RefreshCw className="size-3" /> Refresh</Button>
          </div>
          <div className="mt-4 space-y-3 text-sm">
            <div className="flex items-center justify-between"><span className="flex items-center gap-2"><Server className="size-4" /> API</span><StatusBadge tone={status?.status === "healthy" ? "green" : "red"}>{status?.status || "unknown"}</StatusBadge></div>
            <div className="flex items-center justify-between"><span>Configured</span><span>{status?.configured_provider || "unknown"}</span></div>
            <div className="flex items-center justify-between"><span>Active</span><AIProviderBadge compact /></div>
            <div className="flex items-center justify-between"><span>Model</span><span className="max-w-40 truncate">{status?.model || "-"}</span></div>
            <div className="flex items-center justify-between"><span className="flex items-center gap-2"><Database className="size-4" /> Database</span><span>{status?.database_mode || "-"}</span></div>
            <div className="flex items-center justify-between"><span>Updates</span><StatusBadge tone="green">WebSocket live</StatusBadge></div>
            <p className="text-xs text-slate-500">Last status push: {checkedAt || "not received"}</p>
          </div>
        </Card>
      )}
    </div>
  );
}

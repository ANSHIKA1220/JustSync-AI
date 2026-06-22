/**
 * JourneySync AI – real-time WebSocket layer
 *
 * Architecture
 * ────────────
 * One WebSocket connection is shared across the entire application via
 * React Context (RealtimeProvider).  Components call useRealtime() to
 * register typed event handlers; the provider fans incoming events out to
 * all registered subscribers without re-rendering the tree.
 *
 * Connection lifecycle
 * ────────────────────
 * 1. RealtimeProvider mounts → reads JWT from localStorage → opens WS.
 * 2. Server immediately pushes `provider.status`.
 * 3. Client sends "ping" every 30 s; server replies `{"type":"pong"}`.
 * 4. On unexpected close: reconnect with exponential back-off (1 s → 10 s max).
 * 5. Auth failure (close code 4001): do NOT reconnect.
 * 6. Provider unmounts: socket closed cleanly; reconnect loop cancelled.
 *
 * Fallback
 * ────────
 * If the WS never opens (API down), the initial REST data remains in state.
 * No errors are thrown; a single suppressed console.debug is emitted.
 *
 * Event envelope (from server)
 * ────────────────────────────
 * { "type": "conversation.updated", "data": { ...conversation } }
 * { "type": "conversation.created", "data": { ...conversation } }
 * { "type": "ticket.updated",       "data": { ...ticket }       }
 * { "type": "suggestion.updated",   "data": { ...suggestion }   }
 * { "type": "analytics.updated",    "data": { ...summary }      }
 * { "type": "provider.status",      "data": { ...health }       }
 * { "type": "pong" }
 */

"use client";

import { createContext, useContext, useEffect, useRef, useState } from "react";
import { getToken } from "./api";

// ─── Constants ────────────────────────────────────────────────────────────────
const WS_BASE =
  (process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000").replace(
    /^http/,
    "ws"
  );
const WS_URL = `${WS_BASE}/ws`;

const PING_INTERVAL_MS = 30_000;    // 30 s – matches server heartbeat
const MAX_BACKOFF_MS   = 10_000;    // 10 s ceiling on reconnect delay
const MAX_ATTEMPTS     = 20;        // give up after ~3 min of back-off

// ─── Public types ─────────────────────────────────────────────────────────────

/** All event types the server may push. */
export type WsEventType =
  | "conversation.created"
  | "conversation.updated"
  | "conversation.deleted"
  | "ticket.updated"
  | "suggestion.updated"
  | "analytics.updated"
  | "provider.status"
  | "pong"
  | (string & {}); // allow forward-compatible custom types

export type WsEvent = { type: WsEventType; data?: unknown };

/** Map of event types to handler functions for useRealtime(). */
export type RealtimeHandlers = Partial<Record<WsEventType, (data: unknown) => void>>;

// ─── Internal context ─────────────────────────────────────────────────────────

interface RealtimeCtx {
  /** True when the WebSocket is in OPEN state. */
  connected: boolean;
  /** Register a set of handlers keyed by event type. */
  subscribe: (id: symbol, handlers: RealtimeHandlers) => void;
  /** Deregister a previously registered handler set. */
  unsubscribe: (id: symbol) => void;
}

const RealtimeCtx = createContext<RealtimeCtx | null>(null);

// ─── Provider ─────────────────────────────────────────────────────────────────

/**
 * Wrap the application root with this to enable WebSocket updates.
 * A single socket is created; all useRealtime() subscribers share it.
 */
export function RealtimeProvider({ children }: { children: React.ReactNode }) {
  const [connected, setConnected] = useState(false);

  // Map from subscriber symbol → handler map
  const subscribers = useRef(new Map<symbol, RealtimeHandlers>());

  // Mutable refs so the closure over `connect` always sees the latest values.
  const wsRef            = useRef<WebSocket | null>(null);
  const pingTimerRef     = useRef<ReturnType<typeof setInterval>  | null>(null);
  const reconnectTimerRef= useRef<ReturnType<typeof setTimeout>   | null>(null);
  const attemptRef       = useRef(0);
  const destroyedRef     = useRef(false);

  /** Fan-out an incoming server event to all registered subscribers. */
  function dispatch(event: WsEvent) {
    for (const handlers of subscribers.current.values()) {
      const fn = handlers[event.type as WsEventType];
      if (fn) fn(event.data);
    }
  }

  /** Stop the heartbeat timer. */
  function stopPing() {
    if (pingTimerRef.current) {
      clearInterval(pingTimerRef.current);
      pingTimerRef.current = null;
    }
  }

  /** Open a new WebSocket and wire up all event handlers. */
  function connect() {
    if (destroyedRef.current) return;

    const token = getToken();
    if (!token) {
      // Not logged in – nothing to connect.  Will retry when a new token appears.
      return;
    }

    const url = `${WS_URL}?token=${encodeURIComponent(token)}`;

    let ws: WebSocket;
    try {
      ws = new WebSocket(url);
    } catch {
      // WebSocket constructor can throw in non-browser environments (SSR).
      return;
    }

    wsRef.current = ws;

    ws.onopen = () => {
      attemptRef.current = 0;
      setConnected(true);

      // Start sending pings every 30 s to keep the server connection alive.
      pingTimerRef.current = setInterval(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send("ping");
        }
      }, PING_INTERVAL_MS);
    };

    ws.onmessage = (ev: MessageEvent) => {
      try {
        const msg = JSON.parse(ev.data as string) as WsEvent;
        if (msg.type === "pong") return; // Heartbeat ack – nothing to dispatch.
        dispatch(msg);
      } catch {
        // Ignore malformed frames – never crash on a bad message.
      }
    };

    ws.onclose = (ev: CloseEvent) => {
      stopPing();
      setConnected(false);
      wsRef.current = null;

      if (destroyedRef.current) return;

      // 4001 = auth failure.  Do not retry – token is invalid.
      if (ev.code === 4001) {
        console.debug("[JourneySync WS] Auth rejected (4001) – not reconnecting.");
        return;
      }

      if (attemptRef.current >= MAX_ATTEMPTS) {
        console.debug("[JourneySync WS] Max reconnect attempts reached.");
        return;
      }

      // Exponential back-off: 1 s, 2 s, 4 s, 8 s … capped at 10 s.
      const delay = Math.min(1_000 * 2 ** attemptRef.current, MAX_BACKOFF_MS);
      attemptRef.current += 1;
      reconnectTimerRef.current = setTimeout(connect, delay);
    };

    ws.onerror = () => {
      // Let onclose handle the reconnect logic.
      ws.close();
    };
  }

  useEffect(() => {
    connect();
    return () => {
      destroyedRef.current = true;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      stopPing();
      wsRef.current?.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Run once on mount.

  const subscribe = (id: symbol, handlers: RealtimeHandlers) => {
    subscribers.current.set(id, handlers);
  };

  const unsubscribe = (id: symbol) => {
    subscribers.current.delete(id);
  };

  return (
    <RealtimeCtx.Provider value={{ connected, subscribe, unsubscribe }}>
      {children}
    </RealtimeCtx.Provider>
  );
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

/**
 * Register real-time event handlers for a component.
 *
 * ```tsx
 * useRealtime({
 *   "conversation.updated": (data) => { ... },
 *   "provider.status":      (data) => { ... },
 * });
 * ```
 *
 * • Handlers are updated via ref on every render – no re-subscription needed.
 * • Uses a Proxy so any future event type is automatically forwarded.
 * • Cleans up the subscriber entry on unmount (no memory leaks).
 *
 * @returns `{ connected }` – whether the WebSocket is currently open.
 */
export function useRealtime(handlers: RealtimeHandlers): { connected: boolean } {
  const ctx = useContext(RealtimeCtx);

  // Stable symbol so the same entry is updated (not duplicated) across renders.
  const id = useRef(Symbol("realtime")).current;

  // Always reflect latest handler references without re-registering the subscriber.
  const latestHandlers = useRef(handlers);
  latestHandlers.current = handlers;

  useEffect(() => {
    if (!ctx) return;

    // Proxy forwards every property access to the latest handler map.
    // This lets the provider dispatch any event type without knowing the
    // full set upfront, and handles future event types transparently.
    const proxy = new Proxy({} as RealtimeHandlers, {
      get(_t, prop: string) {
        return (data: unknown) =>
          (latestHandlers.current as Record<string, (d: unknown) => void>)[prop]?.(data);
      },
    });

    ctx.subscribe(id, proxy);
    return () => ctx.unsubscribe(id);
  }, [ctx, id]);

  return { connected: ctx?.connected ?? false };
}

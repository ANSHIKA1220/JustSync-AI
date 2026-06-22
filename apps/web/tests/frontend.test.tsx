import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import DashboardPage from "@/app/dashboard/page";
import LoginPage from "@/app/login/page";
import JourneyMapPage from "@/app/journey-map/page";
import SimulatorPage from "@/app/simulator/page";
import { AIProviderBadge } from "@/components/provider-status";
import { RealtimeProvider, useRealtime } from "@/lib/ws";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { act } from "react";

// ─── Next.js navigation mock ──────────────────────────────────────────────────
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/journey-map",
  useSearchParams: () => new URLSearchParams()
}));

// ─── WebSocket mock ───────────────────────────────────────────────────────────
// Exposes .triggerOpen(), .triggerMessage(json), .triggerClose(code) helpers
// so tests can exercise the hook without a real server.
function createMockWebSocket() {
  const instance = {
    readyState: 0 as number,               // CONNECTING
    send: vi.fn(),
    close: vi.fn(),
    onopen:    null as ((e: Event) => void) | null,
    onmessage: null as ((e: MessageEvent) => void) | null,
    onclose:   null as ((e: CloseEvent) => void) | null,
    onerror:   null as ((e: Event) => void) | null,
    /** Call from tests to simulate a successful connection. */
    triggerOpen() {
      this.readyState = 1; // OPEN
      this.onopen?.(new Event("open"));
    },
    /** Call from tests to push a server event. */
    triggerMessage(data: object) {
      this.onmessage?.(new MessageEvent("message", { data: JSON.stringify(data) }));
    },
    /** Call from tests to simulate a disconnect. */
    triggerClose(code = 1000) {
      this.readyState = 3; // CLOSED
      this.onclose?.(new CloseEvent("close", { code, wasClean: code === 1000 }));
    },
  };
  return instance;
}

type MockWsInstance = ReturnType<typeof createMockWebSocket>;
let lastWsInstance: MockWsInstance | null = null;

const MockWebSocket = vi.fn().mockImplementation((_url: string) => {
  lastWsInstance = createMockWebSocket();
  return lastWsInstance;
});
// Required static constants used by the production code.
(MockWebSocket as any).OPEN = 1;
(MockWebSocket as any).CONNECTING = 0;

// ─── fetch mock ───────────────────────────────────────────────────────────────
const mockFetch = vi.fn(async (input: RequestInfo | URL) => {
  const url = String(input);
  const payload = url.includes("/health")
    ? { status: "healthy", configured_provider: "ollama", active_provider: "mock", fallback_active: true, model: "mock-deterministic", ollama_available: false, database_mode: "sqlite" }
    : url.includes("/analytics/summary")
      ? { active_conversations: 11, open_tickets: 8, avg_first_response_time: 12.9, ai_acceptance_rate: 33.3, customer_satisfaction: 82, escalation_rate: 14, repeat_contact_rate: 37.5, sla_compliance: 91, channel_distribution: [], sentiment_trend: [], ticket_volume: [], high_risk_customers: [], recent_escalations: [] }
      : url.includes("/customers/")
        ? { events: [] }
        : url.includes("/customers")
          ? [{ id: "c1", name: "Priya Shah", loyalty_tier: "Platinum", location: "Mumbai", satisfaction_score: 68, churn_risk_score: 0.82 }]
          : {};
  return new Response(JSON.stringify(payload), { status: 200, headers: { "Content-Type": "application/json" } });
});

// ─── Global setup ─────────────────────────────────────────────────────────────
describe("frontend smoke", () => {
  beforeEach(() => {
    lastWsInstance = null;
    MockWebSocket.mockClear();
    localStorage.setItem("journeysync_token", "test-token");
    vi.stubGlobal("ResizeObserver", class {
      observe() {}
      unobserve() {}
      disconnect() {}
    });
    vi.stubGlobal("fetch", mockFetch);
    vi.stubGlobal("WebSocket", MockWebSocket);
  });

  // ─── Existing smoke tests (unchanged) ────────────────────────────────────────

  it("renders seeded login choices", () => {
    render(<LoginPage />);
    expect(screen.getByText("Support Agent")).toBeInTheDocument();
  });

  it("autofills credentials from a role card", async () => {
    render(<LoginPage />);
    await userEvent.click(screen.getByText("Administrator"));
    expect(screen.getByLabelText("Email")).toHaveValue("admin@journeysync.demo");
    expect(screen.getByLabelText("Password")).toHaveValue("Admin123!");
  });

  it("renders customer journey stages", () => {
    render(<JourneyMapPage />);
    expect(screen.getByText("Delivery")).toBeInTheDocument();
    expect(screen.getByText("Retention")).toBeInTheDocument();
  });

  it("shows provider fallback badge", async () => {
    render(<RealtimeProvider><AIProviderBadge /></RealtimeProvider>);
    expect(await screen.findByText("Mock fallback active")).toBeInTheDocument();
  });

  it("shows chat simulator empty state", async () => {
    render(<RealtimeProvider><SimulatorPage /></RealtimeProvider>);
    expect(await screen.findByText("No interactions yet")).toBeInTheDocument();
  });

  it("renders dashboard date-range controls", async () => {
    render(<RealtimeProvider><DashboardPage /></RealtimeProvider>);
    expect(await screen.findByText("7 days")).toBeInTheDocument();
    expect(screen.getByText("30 days")).toBeInTheDocument();
    expect(screen.getByText("90 days")).toBeInTheDocument();
  });

  // ─── WebSocket smoke tests ────────────────────────────────────────────────────

  it("RealtimeProvider opens a WebSocket on mount", () => {
    render(<RealtimeProvider><div /></RealtimeProvider>);
    expect(MockWebSocket).toHaveBeenCalledTimes(1);
    const calledUrl: string = MockWebSocket.mock.calls[0][0];
    expect(calledUrl).toMatch(/\/ws\?token=/);
  });

  it("useRealtime invokes handler when server pushes a matching event", async () => {
    const onUpdate = vi.fn();

    function TestComponent() {
      useRealtime({ "conversation.updated": onUpdate });
      return null;
    }

    render(
      <RealtimeProvider>
        <TestComponent />
      </RealtimeProvider>
    );

    // Simulate WS connection + server push.
    await act(async () => {
      lastWsInstance?.triggerOpen();
      lastWsInstance?.triggerMessage({ type: "conversation.updated", data: { id: "conv-1" } });
    });

    expect(onUpdate).toHaveBeenCalledWith({ id: "conv-1" });
  });

  it("useRealtime does not invoke handler for unregistered event types", async () => {
    const onUpdate = vi.fn();

    function TestComponent() {
      useRealtime({ "conversation.updated": onUpdate });
      return null;
    }

    render(
      <RealtimeProvider>
        <TestComponent />
      </RealtimeProvider>
    );

    await act(async () => {
      lastWsInstance?.triggerOpen();
      lastWsInstance?.triggerMessage({ type: "ticket.updated", data: { id: "ticket-1" } });
    });

    expect(onUpdate).not.toHaveBeenCalled();
  });

  it("provider.status event updates the AIProviderBadge label", async () => {
    render(
      <RealtimeProvider>
        <AIProviderBadge />
      </RealtimeProvider>
    );

    // Wait for initial REST /health render.
    await screen.findByText("Mock fallback active");

    // Push a provider.status event indicating Ollama is now live.
    await act(async () => {
      lastWsInstance?.triggerOpen();
      lastWsInstance?.triggerMessage({
        type: "provider.status",
        data: {
          status: "healthy",
          configured_provider: "ollama",
          active_provider: "ollama",
          fallback_active: false,
          model: "mistral",
          ollama_available: true,
          database_mode: "sqlite",
        },
      });
    });

    expect(await screen.findByText(/Ollama · mistral/)).toBeInTheDocument();
  });
});

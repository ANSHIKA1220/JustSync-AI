import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import DashboardPage from "@/app/dashboard/page";
import LoginPage from "@/app/login/page";
import JourneyMapPage from "@/app/journey-map/page";
import SimulatorPage from "@/app/simulator/page";
import { AIProviderBadge } from "@/components/provider-status";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/journey-map",
  useSearchParams: () => new URLSearchParams()
}));

describe("frontend smoke", () => {
  beforeEach(() => {
    localStorage.setItem("journeysync_token", "test-token");
    vi.stubGlobal("ResizeObserver", class {
      observe() {}
      unobserve() {}
      disconnect() {}
    });
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      const payload = url.includes("/health")
        ? { status: "healthy", configured_provider: "gemini", active_provider: "mock", fallback_active: true, model: "mock-deterministic", ollama_available: false, database_mode: "sqlite" }
        : url.includes("/organization")
          ? { id: "o1", name: "JourneySync Demo Retail", slug: "journeysync-demo-retail", plan: "enterprise_trial", status: "active", workspaces: [{ id: "w1", organization_id: "o1", name: "Customer Operations", slug: "customer-operations", is_default: true }] }
          : url.endsWith("/users")
            ? [{ id: "u1", email: "agent@journeysync.demo", name: "Sam Support", role: "agent" }]
        : url.includes("/analytics/summary")
          ? { active_conversations: 11, open_tickets: 8, avg_first_response_time: 12.9, ai_acceptance_rate: 33.3, customer_satisfaction: 82, escalation_rate: 14, repeat_contact_rate: 37.5, sla_compliance: 91, channel_distribution: [], sentiment_trend: [], ticket_volume: [], high_risk_customers: [], recent_escalations: [] }
          : url.includes("/customers/")
            ? { events: [] }
            : url.includes("/customers")
              ? [{ id: "c1", name: "Priya Shah", loyalty_tier: "Platinum", location: "Mumbai", satisfaction_score: 68, churn_risk_score: 0.82 }]
              : {};
      return new Response(JSON.stringify(payload), { status: 200, headers: { "Content-Type": "application/json" } });
    }));
  });

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
    render(<AIProviderBadge />);
    expect(await screen.findByText("Mock fallback active")).toBeInTheDocument();
  });

  it("shows chat simulator empty state", async () => {
    render(<SimulatorPage />);
    expect(await screen.findByText("No interactions yet")).toBeInTheDocument();
  });

  it("renders dashboard date-range controls", async () => {
    render(<DashboardPage />);
    expect(await screen.findByText("7 days")).toBeInTheDocument();
    expect(screen.getByText("30 days")).toBeInTheDocument();
    expect(screen.getByText("90 days")).toBeInTheDocument();
  });
});

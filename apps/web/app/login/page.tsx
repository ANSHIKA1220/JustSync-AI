"use client";

import { Button, Card, Input } from "@/components/ui";
import { API_URL, login, signup } from "@/lib/api";
import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowRight, Building2, Eye, EyeOff, Loader2, UserCog } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

const loginSchema = z.object({ email: z.string().trim().email("Enter a valid email."), password: z.string().min(6, "Password must be at least 6 characters.") });
const signupSchema = z.object({
  organizationName: z.string().trim().min(2, "Organization name is required."),
  name: z.string().trim().min(2, "Your name is required."),
  email: z.string().trim().email("Enter a valid work email, for example name@example.com."),
  password: z.string().min(8, "Password must be at least 8 characters.")
});
type LoginValues = z.infer<typeof loginSchema>;
type SignupValues = z.infer<typeof signupSchema>;
type AuthMode = "signup" | "signin";
const creds = [
  { label: "Administrator", email: "admin@journeysync.demo", password: "Admin123!", description: "Analytics, knowledge, routing, and audit controls" },
  { label: "Support Agent", email: "agent@journeysync.demo", password: "Agent123!", description: "Unified inbox, AI suggestions, and customer timelines" },
  { label: "Demo Customer", email: "customer@journeysync.demo", password: "Customer123!", description: "Simulated omnichannel support experience" },
];

function demoModeEnabled() {
  if (process.env.NEXT_PUBLIC_DEMO_MODE === "true" || process.env.NEXT_PUBLIC_SEED_DEMO_DATA === "true" || process.env.SEED_DEMO_DATA === "true") return true;
  if (process.env.NEXT_PUBLIC_DEMO_MODE === "false" || process.env.NEXT_PUBLIC_SEED_DEMO_DATA === "false" || process.env.SEED_DEMO_DATA === "false") return false;
  if (typeof window !== "undefined" && ["localhost", "127.0.0.1"].includes(window.location.hostname)) return true;
  return API_URL.includes("localhost") || API_URL.includes("127.0.0.1");
}

export default function LoginPage() {
  const router = useRouter();
  const demoMode = demoModeEnabled();
  const [mode, setMode] = useState<AuthMode>(demoMode ? "signin" : "signup");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const loginForm = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: demoMode ? { email: "agent@journeysync.demo", password: "Agent123!" } : { email: "", password: "" }
  });
  const signupForm = useForm<SignupValues>({
    resolver: zodResolver(signupSchema),
    defaultValues: { organizationName: "", name: "", email: "", password: "" }
  });
  async function submitLogin(values: LoginValues) {
    setError("");
    setLoading(true);
    try {
      const res = await login(values.email, values.password);
      router.push(res.user.role === "customer" ? "/simulator" : "/dashboard");
    } catch {
      setError(demoMode ? "Incorrect credentials. Choose a demo account or re-enter the password." : "Incorrect credentials. Create an organization first, or sign in with an existing administrator account.");
    } finally {
      setLoading(false);
    }
  }
  async function submitSignup(values: SignupValues) {
    setError("");
    if (values.email.endsWith("@")) {
      setError("Enter the full email address after @, for example anshika@example.com.");
      return;
    }
    setLoading(true);
    try {
      await signup(values.organizationName, values.name, values.email, values.password);
      router.push("/workspace");
    } catch (err) {
      const message = err instanceof Error ? err.message : "";
      setError(message.includes("already registered") ? "That email is already registered. Sign in instead, or use another work email." : message || "Could not create the organization. Check the details and try again.");
    } finally {
      setLoading(false);
    }
  }
  return (
    <main className="grid min-h-screen place-items-center bg-mist p-4 md:p-6">
      <Card className="w-full max-w-5xl overflow-hidden">
        <div className="grid md:grid-cols-[0.95fr_1.05fr]">
          <div className="bg-navy p-8 text-white">
            {demoMode ? <UserCog className="mb-6 size-8 text-pink-300" /> : <Building2 className="mb-6 size-8 text-pink-300" />}
            <h1 className="text-3xl font-bold">{demoMode ? "Launch JourneySync AI" : "Create your JourneySync organization"}</h1>
            <p className="mt-4 text-sm text-slate-200">{demoMode ? "Use one-click seeded credentials for the local demo, or create a fresh organization and load sample data from the workspace." : "Create a clean organization, default workspace, and administrator account. Sample data is loaded only through an explicit in-app action."}</p>
            {demoMode ? (
              <>
                <p className="mt-8 text-xs font-semibold uppercase tracking-wide text-pink-200">Use demo account</p>
                <div className="mt-3 space-y-3">
                  {creds.map((cred) => (
                    <button key={cred.email} type="button" className="focus-ring w-full rounded-md border border-white/15 p-3 text-left text-sm transition hover:bg-white/10" onClick={() => { loginForm.reset({ email: cred.email, password: cred.password }); setMode("signin"); setError(""); }}>
                      <b>{cred.label}</b><span className="block text-slate-300">{cred.email}</span><span className="mt-1 block text-xs text-slate-400">{cred.description}</span>
                    </button>
                  ))}
                </div>
              </>
            ) : (
              <div className="mt-8 rounded-md border border-white/15 bg-white/5 p-4 text-sm text-slate-200">
                <b className="text-white">New production workspace</b>
                <p className="mt-2">Signup creates the organization, default workspace, administrator account, and tenant-scoped access context through the live API.</p>
              </div>
            )}
          </div>
          <div className="flex flex-col justify-center p-8">
            <div className="mb-6 grid grid-cols-2 gap-2 rounded-md bg-slate-100 p-1">
              <button type="button" className={`rounded-md px-3 py-2 text-sm font-semibold ${mode === "signup" ? "bg-white text-navy shadow-sm" : "text-slate-600"}`} onClick={() => { setMode("signup"); setError(""); }}>Create organization</button>
              <button type="button" className={`rounded-md px-3 py-2 text-sm font-semibold ${mode === "signin" ? "bg-white text-navy shadow-sm" : "text-slate-600"}`} onClick={() => { setMode("signin"); setError(""); }}>Sign in</button>
            </div>
            {mode === "signup" ? (
              <form onSubmit={signupForm.handleSubmit(submitSignup)}>
                <label htmlFor="organizationName" className="text-sm font-medium">Organization</label>
                <Input id="organizationName" className="mt-2" autoComplete="organization" {...signupForm.register("organizationName")} />
                {signupForm.formState.errors.organizationName && <p className="mt-2 text-sm text-red-600">{signupForm.formState.errors.organizationName.message}</p>}
                <label htmlFor="name" className="mt-5 block text-sm font-medium">Your name</label>
                <Input id="name" className="mt-2" autoComplete="name" {...signupForm.register("name")} />
                {signupForm.formState.errors.name && <p className="mt-2 text-sm text-red-600">{signupForm.formState.errors.name.message}</p>}
                <label htmlFor="signup-email" className="mt-5 block text-sm font-medium">Work email</label>
                <Input id="signup-email" className="mt-2" autoComplete="email" {...signupForm.register("email")} />
                {signupForm.formState.errors.email && <p className="mt-2 text-sm text-red-600">{signupForm.formState.errors.email.message}</p>}
                <label htmlFor="signup-password" className="mt-5 block text-sm font-medium">Password</label>
                <div className="relative mt-2"><Input id="signup-password" type={showPassword ? "text" : "password"} className="pr-11" autoComplete="new-password" {...signupForm.register("password")} /><button type="button" aria-label={showPassword ? "Hide password" : "Show password"} className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-2 text-slate-500 hover:text-accent" onClick={() => setShowPassword(!showPassword)}>{showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}</button></div>
                {signupForm.formState.errors.password && <p className="mt-2 text-sm text-red-600">{signupForm.formState.errors.password.message}</p>}
                {error && <p role="alert" className="mt-4 rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</p>}
                <Button className="mt-6 w-full" type="submit" disabled={loading}>{loading ? <Loader2 className="size-4 animate-spin" /> : <Building2 className="size-4" />} {loading ? "Creating organization" : "Create organization"}</Button>
              </form>
            ) : (
              <form onSubmit={loginForm.handleSubmit(submitLogin)}>
                {!demoMode && <p className="mb-5 rounded-md bg-amber-50 p-3 text-sm text-amber-800">Create an organization first, then sign in with that administrator account. Each organization sees only its own tenant data.</p>}
                <label htmlFor="email" className="text-sm font-medium">Email</label>
                <Input id="email" className="mt-2" autoComplete="email" {...loginForm.register("email")} />
                {loginForm.formState.errors.email && <p className="mt-2 text-sm text-red-600">{loginForm.formState.errors.email.message}</p>}
                <label htmlFor="password" className="mt-5 block text-sm font-medium">Password</label>
                <div className="relative mt-2"><Input id="password" type={showPassword ? "text" : "password"} className="pr-11" autoComplete="current-password" {...loginForm.register("password")} /><button type="button" aria-label={showPassword ? "Hide password" : "Show password"} className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-2 text-slate-500 hover:text-accent" onClick={() => setShowPassword(!showPassword)}>{showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}</button></div>
                {loginForm.formState.errors.password && <p className="mt-2 text-sm text-red-600">{loginForm.formState.errors.password.message}</p>}
                {error && <p role="alert" className="mt-4 rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</p>}
                <Button className="mt-6 w-full" type="submit" disabled={loading}>{loading ? <Loader2 className="size-4 animate-spin" /> : <ArrowRight className="size-4" />} {loading ? "Signing in" : "Sign in"}</Button>
              </form>
            )}
          </div>
        </div>
      </Card>
    </main>
  );
}

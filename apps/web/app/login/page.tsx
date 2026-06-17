"use client";

import { Button, Card, Input } from "@/components/ui";
import { login } from "@/lib/api";
import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowRight, Eye, EyeOff, Loader2, UserCog } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

const schema = z.object({ email: z.string().email("Enter a valid demo email."), password: z.string().min(6, "Password must be at least 6 characters.") });
type FormValues = z.infer<typeof schema>;
const creds = [
  { label: "Administrator", email: "admin@journeysync.demo", password: "Admin123!", description: "Analytics, knowledge, routing, and audit controls" },
  { label: "Support Agent", email: "agent@journeysync.demo", password: "Agent123!", description: "Unified inbox, AI suggestions, and customer timelines" },
  { label: "Demo Customer", email: "customer@journeysync.demo", password: "Customer123!", description: "Simulated omnichannel support experience" },
];

export default function LoginPage() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const form = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: { email: "agent@journeysync.demo", password: "Agent123!" } });
  async function submit(values: FormValues) {
    setError("");
    setLoading(true);
    try {
      const res = await login(values.email, values.password);
      router.push(res.user.role === "customer" ? "/simulator" : "/dashboard");
    } catch {
      setError("Incorrect credentials. Choose a demo account or re-enter the password.");
    } finally {
      setLoading(false);
    }
  }
  return (
    <main className="grid min-h-screen place-items-center bg-mist p-4 md:p-6">
      <Card className="w-full max-w-5xl overflow-hidden">
        <div className="grid md:grid-cols-[0.95fr_1.05fr]">
          <div className="bg-navy p-8 text-white">
            <UserCog className="mb-6 size-8 text-pink-300" />
            <h1 className="text-3xl font-bold">Launch JourneySync AI</h1>
            <p className="mt-4 text-sm text-slate-200">Use one-click seeded credentials for the local demo. These accounts are not for production.</p>
            <p className="mt-8 text-xs font-semibold uppercase tracking-wide text-pink-200">Use demo account</p>
            <div className="mt-3 space-y-3">
              {creds.map((cred) => (
                <button key={cred.email} type="button" className="focus-ring w-full rounded-md border border-white/15 p-3 text-left text-sm transition hover:bg-white/10" onClick={() => { form.reset({ email: cred.email, password: cred.password }); setError(""); }}>
                  <b>{cred.label}</b><span className="block text-slate-300">{cred.email}</span><span className="mt-1 block text-xs text-slate-400">{cred.description}</span>
                </button>
              ))}
            </div>
          </div>
          <form onSubmit={form.handleSubmit(submit)} className="flex flex-col justify-center p-8">
            <label htmlFor="email" className="text-sm font-medium">Email</label>
            <Input id="email" className="mt-2" autoComplete="email" {...form.register("email")} />
            {form.formState.errors.email && <p className="mt-2 text-sm text-red-600">{form.formState.errors.email.message}</p>}
            <label htmlFor="password" className="mt-5 block text-sm font-medium">Password</label>
            <div className="relative mt-2"><Input id="password" type={showPassword ? "text" : "password"} className="pr-11" autoComplete="current-password" {...form.register("password")} /><button type="button" aria-label={showPassword ? "Hide password" : "Show password"} className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-2 text-slate-500 hover:text-accent" onClick={() => setShowPassword(!showPassword)}>{showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}</button></div>
            {form.formState.errors.password && <p className="mt-2 text-sm text-red-600">{form.formState.errors.password.message}</p>}
            {error && <p role="alert" className="mt-4 rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</p>}
            <Button className="mt-6 w-full" type="submit" disabled={loading}>{loading ? <Loader2 className="size-4 animate-spin" /> : <ArrowRight className="size-4" />} {loading ? "Signing in" : "Sign in"}</Button>
          </form>
        </div>
      </Card>
    </main>
  );
}

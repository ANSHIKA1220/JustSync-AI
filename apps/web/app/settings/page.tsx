"use client";

import { AppShell, PageTitle } from "@/components/app-shell";
import { Badge, Card, EmptyState, Loading, StatusBadge } from "@/components/ui";
import { getOrganization, api, type Organization, type User } from "@/lib/api";
import { Building2, ShieldCheck, UsersRound } from "lucide-react";
import { useEffect, useState } from "react";

export default function SettingsPage() {
  const [organization, setOrganization] = useState<Organization | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getOrganization(), api<User[]>("/users")])
      .then(([org, orgUsers]) => {
        setOrganization(org);
        setUsers(orgUsers);
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <AppShell>
      <PageTitle title="Organization Settings" subtitle="Manage the SaaS workspace foundation for tenant-scoped support operations." />
      {loading ? <Loading /> : !organization ? <EmptyState title="Organization unavailable" description="Sign in again to reload tenant context." /> : (
        <div className="grid gap-5 lg:grid-cols-[1fr_1.2fr]">
          <Card className="p-5">
            <div className="flex items-start gap-3">
              <span className="rounded-md bg-blush p-2 text-accent"><Building2 className="size-5" /></span>
              <div>
                <h2 className="text-lg font-semibold text-navy">{organization.name}</h2>
                <p className="mt-1 text-sm text-slate-500">Tenant slug: {organization.slug}</p>
                <div className="mt-3 flex gap-2">
                  <StatusBadge tone="green">{organization.status}</StatusBadge>
                  <Badge>{organization.plan}</Badge>
                </div>
              </div>
            </div>
            <div className="mt-6 border-t border-slate-200 pt-4">
              <h3 className="text-sm font-semibold text-navy">Workspaces</h3>
              <div className="mt-3 space-y-2">
                {organization.workspaces.map((workspace) => (
                  <div key={workspace.id} className="flex items-center justify-between rounded-md border border-slate-200 p-3 text-sm">
                    <span>{workspace.name}</span>
                    {workspace.is_default && <StatusBadge tone="slate">Default</StatusBadge>}
                  </div>
                ))}
              </div>
            </div>
          </Card>
          <Card className="p-5">
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <UsersRound className="size-5 text-accent" />
                <h2 className="text-lg font-semibold text-navy">Team Access</h2>
              </div>
              <StatusBadge tone="green">{users.length} users</StatusBadge>
            </div>
            <div className="divide-y divide-slate-100">
              {users.map((user) => (
                <div key={user.id} className="flex items-center justify-between py-3 text-sm">
                  <div>
                    <p className="font-medium text-ink">{user.name}</p>
                    <p className="text-slate-500">{user.email}</p>
                  </div>
                  <Badge>{user.role}</Badge>
                </div>
              ))}
            </div>
          </Card>
          <Card className="p-5 lg:col-span-2">
            <div className="flex gap-3 text-sm text-slate-600">
              <ShieldCheck className="size-5 text-accent" />
              <p>Tenant-scoped APIs are active for users, customers, conversations, knowledge, routing rules, analytics, and audit logs. This is the foundation for real connectors, billing limits, AI usage accounting, and enterprise permissions.</p>
            </div>
          </Card>
        </div>
      )}
    </AppShell>
  );
}

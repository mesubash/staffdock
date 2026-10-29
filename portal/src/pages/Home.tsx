import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { ChevronRight } from "lucide-react";

import { Card, Empty, ErrorText, Page, StatusBadge, formatDate } from "@/components/common";
import { call, type Tasks } from "@/lib/api";
import { CheckInCard } from "@/pages/Attendance";
import { leaveDates } from "@/pages/Leave";
import { useMe } from "@/lib/session";

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
}

type Item = { key: string; to: string; params?: Record<string, string>; title: string; detail: string; state?: [string, string] };

export function Home() {
  const me = useMe();
  const tasks = useQuery({ queryKey: ["tasks"], queryFn: () => call<Tasks>("staffdock.api.my_tasks") });
  const t = tasks.data;

  const items: Item[] = t
    ? [
        ...t.requests_to_acknowledge.map((r) => ({
          key: `ack-${r.name}`,
          to: "/requests/$name",
          params: { name: r.name },
          title: `Confirm you received ${r.name}`,
          detail: r.sd_reason || "Items were issued to you",
        })),
        ...t.assets_to_acknowledge.map((a) => ({
          key: `asset-${a.name}`,
          to: "/assets",
          title: `Confirm you received ${a.asset_name}`,
          detail: a.asset,
        })),
        ...t.to_approve.map((r) => ({
          key: `appr-${r.name}`,
          to: "/requests/$name",
          params: { name: r.name },
          title: `Approve ${r.sd_employee_name}'s request`,
          detail: r.sd_reason || r.name,
          state: [r.workflow_state, r.status] as [string, string],
        })),
        ...t.leaves_to_approve.map((l) => ({
          key: `leave-${l.name}`,
          to: "/approvals",
          title: `Approve ${l.employee_name}'s ${l.leave_type}`,
          detail: leaveDates(l),
        })),
        ...(t.to_review ?? []).map((r) => ({
          key: `rev-${r.name}`,
          to: "/requests/$name",
          params: { name: r.name },
          title: `Review ${r.sd_employee_name}'s request`,
          detail: r.sd_reason || r.name,
          state: [r.workflow_state, r.status] as [string, string],
        })),
        ...(t.to_issue ?? []).map((r) => ({
          key: `iss-${r.name}`,
          to: "/requests/$name",
          params: { name: r.name },
          title: `Issue items for ${r.sd_employee_name}`,
          detail: r.sd_reason || r.name,
          state: [r.workflow_state, r.status] as [string, string],
        })),
      ]
    : [];

  return (
    <Page title={`${greeting()}, ${me.full_name.split(" ")[0]}`}>
      {me.employee ? <CheckInCard /> : null}

      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="Waiting on you" value={items.length} />
        <Stat label="My open requests" value={t?.open_requests} to="/requests" />
        <Stat label="Assets with me" value={t?.my_assets} to="/assets" />
      </div>

      <Card title="Needs your attention">
        <ErrorText error={tasks.error} />
        {tasks.isLoading ? <Empty>Loading…</Empty> : null}
        {t && items.length === 0 ? <Empty>Nothing waiting on you.</Empty> : null}
        <ul className="divide-y divide-border">
          {items.map((i) => (
            <li key={i.key}>
              <Link to={i.to} params={i.params} className="flex items-center gap-3 py-3 hover:bg-accent/50">
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">{i.title}</p>
                  <p className="truncate text-sm text-muted-foreground">{i.detail}</p>
                </div>
                {i.state ? <StatusBadge state={i.state[0]} status={i.state[1]} /> : null}
                <ChevronRight className="size-4 text-muted-foreground" />
              </Link>
            </li>
          ))}
        </ul>
      </Card>

      <Updates />

      <div>
        <Link to="/requests/new" className="text-sm font-medium text-primary underline-offset-4 hover:underline">
          + Request items or equipment
        </Link>
      </div>
    </Page>
  );
}

function Stat({ label, value, to }: { label: string; value?: number; to?: string }) {
  const body = (
    <div className="rounded-xl border border-border bg-card p-4">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="mt-1 text-2xl font-semibold">{value ?? "–"}</p>
    </div>
  );
  return to ? (
    <Link to={to} className="hover:opacity-90">
      {body}
    </Link>
  ) : (
    body
  );
}

type Update = { subject: string; document_type: string; document_name: string; creation: string };

function Updates() {
  const updates = useQuery({ queryKey: ["updates"], queryFn: () => call<Update[]>("staffdock.api.updates") });
  if (!updates.data?.length) return null;
  return (
    <Card title="Recent updates">
      <ul className="divide-y divide-border">
        {updates.data.map((u, i) => {
          const body = (
            <div className="flex items-center gap-3 py-3">
              <p className="min-w-0 flex-1 text-sm">{u.subject.replace(/<[^>]+>/g, "")}</p>
              <span className="text-xs whitespace-nowrap text-muted-foreground">{formatDate(u.creation)}</span>
            </div>
          );
          return (
            <li key={i}>
              {u.document_type === "Material Request" ? (
                <Link to="/requests/$name" params={{ name: u.document_name }} className="block hover:bg-accent/50">
                  {body}
                </Link>
              ) : u.document_type === "Asset Movement" ? (
                <Link to="/assets" className="block hover:bg-accent/50">
                  {body}
                </Link>
              ) : (
                body
              )}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

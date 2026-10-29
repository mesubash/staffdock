import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Card, Empty, ErrorText, Page, formatDate, selectClass } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { call } from "@/lib/api";
import { cn } from "@/lib/utils";

export type LeaveRow = {
  name: string;
  employee_name: string;
  leave_type: string;
  from_date: string;
  to_date: string;
  half_day: number;
  total_leave_days: number;
  description?: string;
  status: string;
  docstatus: number;
  leave_approver_name?: string;
};

type Summary = {
  balances: { leave_type: string; total: number; taken: number; pending: number; remaining: number }[];
  applications: LeaveRow[];
};

const LEAVE_STYLE: Record<string, string> = {
  Open: "bg-amber-100 text-amber-800",
  Approved: "bg-green-100 text-green-800",
  Rejected: "bg-red-100 text-red-800",
  Cancelled: "bg-muted text-muted-foreground",
};

export function LeaveStatus({ status }: { status: string }) {
  return (
    <span className={cn("inline-flex rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap", LEAVE_STYLE[status] ?? "bg-muted")}>
      {status === "Open" ? "Waiting for approval" : status}
    </span>
  );
}

export function leaveDates(l: LeaveRow) {
  const days = `${l.total_leave_days} day${l.total_leave_days === 1 ? "" : "s"}`;
  return l.from_date === l.to_date ? `${formatDate(l.from_date)} · ${days}` : `${formatDate(l.from_date)} – ${formatDate(l.to_date)} · ${days}`;
}

export function Leave() {
  const queryClient = useQueryClient();
  const summary = useQuery({ queryKey: ["leave"], queryFn: () => call<Summary>("staffdock.api.leave_summary") });
  const done = () => queryClient.invalidateQueries();
  const withdraw = useMutation({ mutationFn: (name: string) => call("staffdock.api.withdraw_leave", { name }), onSuccess: done });
  const [applying, setApplying] = useState(false);

  const s = summary.data;
  return (
    <Page
      title="Leave"
      actions={
        s?.balances.some((b) => b.remaining > 0) && !applying ? <Button onClick={() => setApplying(true)}>Apply for leave</Button> : null
      }
    >
      <ErrorText error={summary.error} />
      {s && s.balances.length === 0 ? (
        <Card>
          <Empty>No leave has been allocated to you yet. Contact HR.</Empty>
        </Card>
      ) : null}
      {s?.balances.length ? (
        <div className="grid gap-4 sm:grid-cols-3">
          {s.balances.map((b) => (
            <div key={b.leave_type} className="rounded-xl border border-border bg-card p-4">
              <p className="text-sm text-muted-foreground">{b.leave_type}</p>
              <p className="mt-1 text-2xl font-semibold">
                {b.remaining} <span className="text-sm font-normal text-muted-foreground">of {b.total} left</span>
              </p>
              {b.pending ? <p className="mt-1 text-xs text-muted-foreground">{b.pending} waiting for approval</p> : null}
            </div>
          ))}
        </div>
      ) : null}

      {s?.balances.length ? (
        applying ? (
          <ApplyForm
            types={s.balances.filter((b) => b.remaining > 0).map((b) => b.leave_type)}
            onDone={() => {
              setApplying(false);
              done();
            }}
            onCancel={() => setApplying(false)}
          />
        ) : null
      ) : null}

      <Card title="My leave">
        <ErrorText error={withdraw.error} />
        {s?.applications.length === 0 ? <Empty>You haven't applied for leave yet.</Empty> : null}
        <ul className="divide-y divide-border">
          {s?.applications.map((l) => (
            <li key={l.name} className="flex flex-wrap items-center gap-3 py-3">
              <div className="min-w-48 flex-1">
                <p className="text-sm font-medium">{l.leave_type}</p>
                <p className="text-sm text-muted-foreground">{leaveDates(l)}</p>
                {l.status === "Open" && l.leave_approver_name ? (
                  <p className="text-xs text-muted-foreground">Waiting for {l.leave_approver_name}</p>
                ) : null}
              </div>
              <LeaveStatus status={l.status} />
              {l.status === "Open" && l.docstatus === 0 ? (
                <Button size="sm" variant="ghost" disabled={withdraw.isPending} onClick={() => withdraw.mutate(l.name)}>
                  Withdraw
                </Button>
              ) : null}
            </li>
          ))}
        </ul>
      </Card>
    </Page>
  );
}

function ApplyForm({ types, onDone, onCancel }: { types: string[]; onDone: () => void; onCancel: () => void }) {
  const today = new Date().toISOString().slice(0, 10);
  const empty = { leave_type: types[0] ?? "", from_date: today, to_date: today, half_day: false, reason: "" };
  const [form, setForm] = useState(empty);
  const apply = useMutation({
    mutationFn: () => call("staffdock.api.apply_leave", { ...form, half_day: form.half_day ? 1 : 0 }),
    onSuccess: () => {
      setForm(empty);
      onDone();
    },
  });
  const oneDay = form.from_date === form.to_date;
  const valid = form.leave_type && form.from_date && form.to_date >= form.from_date && form.reason.trim();

  if (!types.length) return null;
  return (
    <Card title="Apply for leave">
      <form
        className="flex flex-col gap-4"
        onSubmit={(e) => {
          e.preventDefault();
          if (valid) apply.mutate();
        }}
      >
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="leave-type">Type</Label>
            <select
              id="leave-type"
              className={selectClass}
              value={form.leave_type}
              onChange={(e) => setForm({ ...form, leave_type: e.target.value })}
            >
              {types.map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="leave-from">From</Label>
            <Input
              id="leave-from"
              type="date"
              value={form.from_date}
              onChange={(e) => setForm({ ...form, from_date: e.target.value, to_date: e.target.value > form.to_date ? e.target.value : form.to_date })}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="leave-to">To</Label>
            <Input id="leave-to" type="date" min={form.from_date} value={form.to_date} onChange={(e) => setForm({ ...form, to_date: e.target.value })} />
          </div>
        </div>
        {oneDay ? (
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={form.half_day} onChange={(e) => setForm({ ...form, half_day: e.target.checked })} />
            Half day
          </label>
        ) : null}
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="leave-reason">Reason</Label>
          <Input id="leave-reason" value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} placeholder="e.g. Family event" />
        </div>
        <ErrorText error={apply.error} />
        <div className="flex gap-2">
          <Button type="submit" disabled={!valid || apply.isPending}>
            {apply.isPending ? "Sending…" : "Apply"}
          </Button>
          <Button type="button" variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
        </div>
      </form>
    </Card>
  );
}

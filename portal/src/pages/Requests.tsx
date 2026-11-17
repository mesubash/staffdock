import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "@tanstack/react-router";
import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { ACTION_LABELS, Card, ConfirmButton, Empty, ErrorText, HISTORY_LABELS, Page, Skeleton, StatusBadge, formatDate, selectClass } from "@/components/common";
import { useToast } from "@/components/toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { applyAction, call, getActions, getDoc, getList, insert, type RequestRow } from "@/lib/api";
import { useMe } from "@/lib/session";
import { cn } from "@/lib/utils";

const ROW_FIELDS = ["name", "sd_employee_name", "sd_reason", "workflow_state", "status", "modified"];
const CLOSED = ["Completed", "Manager Rejected", "Inventory Rejected", "Closed"];

// Toast after a workflow action
const DONE_MESSAGES: Record<string, string> = {
  Submit: "Sent for approval",
  Approve: "Approved",
  Reject: "Rejected",
  Close: "Request closed",
  "Acknowledge Receipt": "Receipt confirmed",
};

export function RequestsList() {
  const me = useMe();
  const mine = useQuery({
    queryKey: ["requests", "mine"],
    queryFn: () => getList<RequestRow>("Material Request", { fields: ROW_FIELDS, filters: { owner: me.user } }),
  });
  const [filter, setFilter] = useState<"Open" | "All">("Open");
  const rows = mine.data?.filter((r) => filter === "All" || !CLOSED.includes(r.workflow_state));

  return (
    <Page
      title="My requests"
      actions={
        <Button asChild>
          <Link to="/requests/new">
            <Plus /> New request
          </Link>
        </Button>
      }
    >
      <div className="flex gap-1 self-start rounded-lg bg-muted p-1">
        {(["Open", "All"] as const).map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => setFilter(f)}
            className={cn("cursor-pointer rounded-md px-4 py-1.5 text-sm", filter === f ? "bg-card font-medium shadow-sm" : "text-muted-foreground")}
          >
            {f}
          </button>
        ))}
      </div>
      <Card>
        <ErrorText error={mine.error} />
        {mine.isLoading ? <Skeleton /> : null}
        {rows && rows.length === 0 ? <Empty>{filter === "Open" ? "No open requests." : "You haven't requested anything yet."}</Empty> : null}
        <RequestTable rows={rows ?? []} />
      </Card>
    </Page>
  );
}

export function RequestTable({ rows, showRequester }: { rows: RequestRow[]; showRequester?: boolean }) {
  if (!rows.length) return null;
  return (
    <ul className="divide-y divide-border">
      {rows.map((r) => (
        <li key={r.name}>
          <Link
            to="/requests/$name"
            params={{ name: r.name }}
            className="flex flex-wrap items-center gap-x-4 gap-y-1 py-3 hover:bg-accent/50"
          >
            <span className="w-36 text-sm font-medium">{r.name}</span>
            {showRequester ? <span className="w-36 text-sm">{r.sd_employee_name}</span> : null}
            <span className="min-w-0 flex-1 truncate text-sm text-muted-foreground">{r.sd_reason}</span>
            <span className="text-xs text-muted-foreground">{formatDate(r.modified)}</span>
            <StatusBadge state={r.workflow_state} status={r.status} />
          </Link>
        </li>
      ))}
    </ul>
  );
}

type ItemOption = { name: string; item_name: string; stock_uom: string };
type Line = { item_code: string; qty: string };

function inDays(days: number) {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

export function RequestNew() {
  const me = useMe();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const items = useQuery({
    queryKey: ["items"],
    queryFn: () =>
      getList<ItemOption>("Item", {
        fields: ["name", "item_name", "stock_uom"],
        filters: { disabled: 0, is_stock_item: 1 },
        orderBy: "item_name asc",
        limit: 500,
      }),
  });
  const toast = useToast();
  const [lines, setLines] = useState<Line[]>([{ item_code: "", qty: "1" }]);
  const [requiredBy, setRequiredBy] = useState(inDays(3));
  const [reason, setReason] = useState("");

  const send = useMutation({
    mutationFn: async () => {
      const doc = await insert<Record<string, unknown>>("Material Request", {
        material_request_type: "Material Issue",
        schedule_date: requiredBy,
        sd_reason: reason,
        items: lines.map((l) => ({
          item_code: l.item_code,
          qty: Number(l.qty),
          schedule_date: requiredBy,
          warehouse: me.default_warehouse,
        })),
      });
      await applyAction(doc, "Submit");
      return doc.name as string;
    },
    onSuccess: (name) => {
      queryClient.invalidateQueries();
      toast("Request sent");
      navigate({ to: "/requests/$name", params: { name } });
    },
  });

  const valid = reason.trim() && lines.every((l) => l.item_code && Number(l.qty) > 0);
  const update = (i: number, patch: Partial<Line>) => setLines(lines.map((l, j) => (i === j ? { ...l, ...patch } : l)));

  return (
    <Page title="New request">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (valid) send.mutate();
        }}
      >
        <Card>
          <div className="flex flex-col gap-5">
            <div className="flex flex-col gap-2">
              <Label>Items</Label>
              {lines.map((l, i) => (
                <div key={i} className="flex gap-2">
                  <select
                    aria-label="Item"
                    className={selectClass}
                    value={l.item_code}
                    onChange={(e) => update(i, { item_code: e.target.value })}
                  >
                    <option value="">Choose an item…</option>
                    {items.data?.map((it) => (
                      <option key={it.name} value={it.name}>
                        {it.item_name}
                      </option>
                    ))}
                  </select>
                  <Input
                    aria-label="Quantity"
                    type="number"
                    min="1"
                    className="w-24"
                    value={l.qty}
                    onChange={(e) => update(i, { qty: e.target.value })}
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    aria-label="Remove item"
                    disabled={lines.length === 1}
                    onClick={() => setLines(lines.filter((_, j) => j !== i))}
                  >
                    <Trash2 />
                  </Button>
                </div>
              ))}
              <div>
                <Button type="button" variant="outline" size="sm" onClick={() => setLines([...lines, { item_code: "", qty: "1" }])}>
                  <Plus /> Add another item
                </Button>
              </div>
            </div>

            <div className="grid gap-5 sm:grid-cols-[200px_1fr]">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="required-by">Needed by</Label>
                <Input id="required-by" type="date" min={inDays(0)} value={requiredBy} onChange={(e) => setRequiredBy(e.target.value)} />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="reason">Why do you need it?</Label>
                <Input id="reason" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Field trip to Lukla" />
              </div>
            </div>

            <ErrorText error={send.error} />
            <div className="flex gap-2">
              <Button type="submit" disabled={!valid || send.isPending}>
                {send.isPending ? "Sending…" : "Send request"}
              </Button>
              <Button type="button" variant="ghost" onClick={() => navigate({ to: "/requests" })}>
                Cancel
              </Button>
            </div>
          </div>
        </Card>
      </form>
    </Page>
  );
}

type RequestDoc = RequestRow & {
  owner: string;
  docstatus: number;
  sd_approver?: string;
  sd_approver_name?: string;
  schedule_date: string;
  transaction_date: string;
  per_ordered: number;
  items: { name: string; item_code: string; item_name: string; qty: number; uom: string; ordered_qty: number }[];
};

export function RequestDetail() {
  const { name } = useParams({ from: "/requests/$name" });
  const me = useMe();
  const queryClient = useQueryClient();
  const doc = useQuery({ queryKey: ["request", name], queryFn: () => getDoc<RequestDoc>("Material Request", name) });
  const actions = useQuery({
    queryKey: ["request", name, "actions"],
    queryFn: () => getActions(doc.data),
    enabled: !!doc.data,
  });

  const toast = useToast();
  const done = (message: string) => {
    queryClient.invalidateQueries();
    toast(message);
  };
  const act = useMutation({
    mutationFn: (action: string) => applyAction(doc.data, action),
    onSuccess: (_, action) => done(DONE_MESSAGES[action] ?? "Done"),
  });
  const issue = useMutation({ mutationFn: () => call("staffdock.api.issue_request", { name }), onSuccess: () => done("Items issued") });
  const navigate = useNavigate();
  const discard = useMutation({
    mutationFn: () => call("staffdock.api.discard_request", { name }),
    onSuccess: () => {
      queryClient.invalidateQueries();
      toast("Draft discarded");
      navigate({ to: "/requests" });
    },
  });

  if (doc.error) return <Page title={name}><ErrorText error={doc.error} /></Page>;
  if (!doc.data) return <Page title={name}><Skeleton rows={4} /></Page>;
  const d = doc.data;
  const canIssue = me.is_inventory && d.workflow_state === "Approved" && d.status !== "Issued";
  const canDiscard = d.owner === me.user && d.docstatus === 0 && (!d.workflow_state || d.workflow_state === "Draft");
  const waitingFor = waitingOn(d, me.user);

  return (
    <Page title={`Request ${d.name}`} actions={<StatusBadge state={d.workflow_state} status={d.status} />}>
      <Card>
        <dl className="grid gap-4 text-sm sm:grid-cols-4">
          <Field label="Requested by" value={d.sd_employee_name} />
          <Field label="Requested on" value={formatDate(d.transaction_date)} />
          <Field label="Needed by" value={formatDate(d.schedule_date)} />
          <Field label="Reason" value={d.sd_reason} />
        </dl>
        {waitingFor ? (
          <p className="mt-4 rounded-md bg-muted px-3 py-2 text-sm">
            Waiting for <span className="font-medium">{waitingFor}</span>
          </p>
        ) : null}
      </Card>

      <Card title="Items">
        <table className="w-full text-sm">
          <thead className="text-left text-muted-foreground">
            <tr>
              <th className="pb-2 font-normal">Item</th>
              <th className="pb-2 text-right font-normal">Requested</th>
              <th className="pb-2 text-right font-normal">Issued</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {d.items.map((it) => (
              <tr key={it.name}>
                <td className="py-2">{it.item_name}</td>
                <td className="py-2 text-right">
                  {it.qty} {it.uom}
                </td>
                <td className="py-2 text-right">{it.ordered_qty || 0}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      {actions.data?.length || canIssue || canDiscard ? (
        <Card title="What would you like to do?">
          <ErrorText error={act.error ?? issue.error ?? discard.error} />
          <div className="flex flex-wrap gap-2">
            {canIssue ? (
              <Button disabled={issue.isPending} onClick={() => issue.mutate()}>
                {issue.isPending ? "Issuing…" : "Issue items from store"}
              </Button>
            ) : null}
            {actions.data?.map((t) =>
              /reject|close/i.test(t.action) ? (
                <ConfirmButton
                  key={t.action}
                  variant={t.action === "Close" ? "outline" : "destructive"}
                  confirmLabel={`Click again to ${(ACTION_LABELS[t.action] ?? t.action).toLowerCase()}`}
                  disabled={act.isPending}
                  onConfirm={() => act.mutate(t.action)}
                >
                  {ACTION_LABELS[t.action] ?? t.action}
                </ConfirmButton>
              ) : (
                <Button key={t.action} variant={canIssue ? "outline" : "default"} disabled={act.isPending} onClick={() => act.mutate(t.action)}>
                  {ACTION_LABELS[t.action] ?? t.action}
                </Button>
              ),
            )}
            {canDiscard ? (
              <ConfirmButton variant="ghost" confirmLabel="Click again to discard" disabled={discard.isPending} onConfirm={() => discard.mutate()}>
                Discard
              </ConfirmButton>
            ) : null}
          </div>
        </Card>
      ) : null}

      <History doctype="Material Request" name={d.name} />
    </Page>
  );
}

/** Who has to act next, in plain words. */
function waitingOn(d: RequestDoc, user: string): string | null {
  switch (d.workflow_state) {
    case "Pending Manager Approval":
      return d.sd_approver === user ? "you to approve" : `${d.sd_approver_name || "the manager"} to approve`;
    case "Pending Inventory Review":
      return "the inventory team to review";
    case "Approved":
      if (d.status !== "Issued") return "the inventory team to issue the items";
      return d.owner === user ? "you to confirm you received the items" : `${d.sd_employee_name} to confirm receipt`;
    default:
      return null;
  }
}

type Event = { at: string; by: string; text: string };

function History({ doctype, name }: { doctype: string; name: string }) {
  const events = useQuery({
    queryKey: ["history", doctype, name],
    queryFn: () => call<Event[]>("staffdock.api.history", { doctype, name }),
  });
  if (!events.data?.length) return null;
  return (
    <Card title="History">
      <ol className="flex flex-col gap-3">
        {events.data.map((e, i) => (
          <li key={i} className="flex gap-3 text-sm">
            <span className="mt-1.5 size-2 shrink-0 rounded-full bg-primary/60" />
            <div>
              <p>
                <span className="font-medium">{HISTORY_LABELS[e.text] ?? e.text}</span>
                <span className="text-muted-foreground"> · {e.by}</span>
              </p>
              <p className="text-xs text-muted-foreground">
                {new Date(e.at.replace(" ", "T")).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}
              </p>
            </div>
          </li>
        ))}
      </ol>
    </Card>
  );
}

function Field({ label, value }: { label: string; value?: string }) {
  return (
    <div>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 font-medium">{value || "—"}</dd>
    </div>
  );
}

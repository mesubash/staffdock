import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Paperclip, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { Card, ConfirmButton, Empty, ErrorText, Page, Skeleton, formatDate, selectClass } from "@/components/common";
import { useToast } from "@/components/toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { call, uploadFile } from "@/lib/api";
import { cn } from "@/lib/utils";

export type Claim = {
  name: string;
  employee_name: string;
  posting_date: string;
  total_claimed_amount: number;
  approval_status: string;
  status: string;
  docstatus: number;
  remark?: string;
  currency: string;
  lines: { expense_date: string; expense_type: string; description?: string; amount: number }[];
  receipts: { file_name: string; file_url: string }[];
};

export function money(amount: number, currency: string) {
  return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(amount || 0);
}

function claimState(c: Claim): [string, string] {
  if (c.approval_status === "Rejected") return ["Rejected", "bg-red-100 text-red-800"];
  if (c.status === "Paid") return ["Paid", "bg-green-100 text-green-800"];
  if (c.approval_status === "Approved") return ["Approved, to be paid", "bg-blue-100 text-blue-800"];
  return ["Waiting for approval", "bg-amber-100 text-amber-800"];
}

export function ClaimStatus({ claim }: { claim: Claim }) {
  const [label, tone] = claimState(claim);
  return <span className={cn("inline-flex rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap", tone)}>{label}</span>;
}

export function ClaimLines({ claim }: { claim: Claim }) {
  return (
    <div className="mt-2 flex flex-col gap-1 text-sm text-muted-foreground">
      {claim.lines.map((l, i) => (
        <p key={i}>
          {formatDate(l.expense_date)} · {l.expense_type} · {money(l.amount, claim.currency)}
          {l.description ? ` · ${l.description.replace(/<[^>]+>/g, "")}` : ""}
        </p>
      ))}
      {claim.receipts.map((r) => (
        <a key={r.file_url} href={r.file_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-primary underline-offset-4 hover:underline">
          <Paperclip className="size-3.5" /> {r.file_name}
        </a>
      ))}
    </div>
  );
}

export function Expenses() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const data = useQuery({ queryKey: ["expenses"], queryFn: () => call<{ types: string[]; claims: Claim[] }>("staffdock.api.my_expenses") });
  const [creating, setCreating] = useState(false);
  const withdraw = useMutation({
    mutationFn: (name: string) => call("staffdock.api.withdraw_expense", { name }),
    onSuccess: () => {
      queryClient.invalidateQueries();
      toast("Claim withdrawn");
    },
  });

  return (
    <Page title="Expenses" actions={!creating ? <Button onClick={() => setCreating(true)}>New claim</Button> : null}>
      <ErrorText error={data.error ?? withdraw.error} />
      {data.isLoading ? <Skeleton /> : null}
      {creating && data.data ? <ClaimForm types={data.data.types} onClose={() => setCreating(false)} /> : null}
      <Card title="My claims">
        {data.data?.claims.length === 0 ? <Empty>You haven't claimed any expenses yet.</Empty> : null}
        <ul className="divide-y divide-border">
          {data.data?.claims.map((c) => (
            <li key={c.name} className="py-3">
              <div className="flex flex-wrap items-center gap-3">
                <div className="min-w-48 flex-1">
                  <p className="text-sm font-medium">
                    {money(c.total_claimed_amount, c.currency)} <span className="font-normal text-muted-foreground">· {formatDate(c.posting_date)}</span>
                  </p>
                  {c.remark ? <p className="text-sm text-muted-foreground">{c.remark}</p> : null}
                </div>
                <ClaimStatus claim={c} />
                {c.docstatus === 0 && c.approval_status === "Draft" ? (
                  <ConfirmButton size="sm" variant="ghost" confirmLabel="Click again to withdraw" disabled={withdraw.isPending} onConfirm={() => withdraw.mutate(c.name)}>
                    Withdraw
                  </ConfirmButton>
                ) : null}
              </div>
              <ClaimLines claim={c} />
            </li>
          ))}
        </ul>
      </Card>
    </Page>
  );
}

type Line = { expense_date: string; expense_type: string; amount: string; description: string };

function ClaimForm({ types, onClose }: { types: string[]; onClose: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const today = new Date().toISOString().slice(0, 10);
  const blank = (): Line => ({ expense_date: today, expense_type: types[0] ?? "", amount: "", description: "" });
  const [lines, setLines] = useState<Line[]>([blank()]);
  const [remark, setRemark] = useState("");
  const [receipt, setReceipt] = useState<File | null>(null);
  const submit = useMutation({
    mutationFn: async () =>
      call("staffdock.api.submit_expense", {
        lines,
        remark,
        receipt_url: receipt ? await uploadFile(receipt, true) : null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries();
      toast("Claim sent for approval");
      onClose();
    },
  });
  const update = (i: number, patch: Partial<Line>) => setLines(lines.map((l, j) => (i === j ? { ...l, ...patch } : l)));
  const valid = lines.every((l) => l.expense_date && l.expense_type && Number(l.amount) > 0);

  return (
    <Card title="New expense claim">
      <form
        className="flex flex-col gap-4"
        onSubmit={(e) => {
          e.preventDefault();
          if (valid) submit.mutate();
        }}
      >
        {lines.map((l, i) => (
          <div key={i} className="grid gap-2 sm:grid-cols-[150px_150px_120px_1fr_auto] sm:items-end">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor={`date-${i}`}>Date</Label>
              <Input id={`date-${i}`} type="date" max={today} value={l.expense_date} onChange={(e) => update(i, { expense_date: e.target.value })} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor={`type-${i}`}>Type</Label>
              <select id={`type-${i}`} className={selectClass} value={l.expense_type} onChange={(e) => update(i, { expense_type: e.target.value })}>
                {types.map((t) => (
                  <option key={t}>{t}</option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor={`amount-${i}`}>Amount</Label>
              <Input id={`amount-${i}`} type="number" min="0" step="0.01" value={l.amount} onChange={(e) => update(i, { amount: e.target.value })} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor={`desc-${i}`}>What for</Label>
              <Input id={`desc-${i}`} value={l.description} onChange={(e) => update(i, { description: e.target.value })} placeholder="e.g. Taxi to client" />
            </div>
            <Button type="button" variant="ghost" size="icon" aria-label="Remove expense" disabled={lines.length === 1} onClick={() => setLines(lines.filter((_, j) => j !== i))}>
              <Trash2 />
            </Button>
          </div>
        ))}
        <div>
          <Button type="button" variant="outline" size="sm" onClick={() => setLines([...lines, blank()])}>
            <Plus /> Add another expense
          </Button>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="remark">Note (optional)</Label>
            <Input id="remark" value={remark} onChange={(e) => setRemark(e.target.value)} placeholder="e.g. Client visit in Boston" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="receipt">Receipt (optional)</Label>
            <Input id="receipt" type="file" accept="image/*,application/pdf" onChange={(e) => setReceipt(e.target.files?.[0] ?? null)} />
          </div>
        </div>
        <ErrorText error={submit.error} />
        <div className="flex gap-2">
          <Button type="submit" disabled={!valid || submit.isPending}>
            {submit.isPending ? "Sending…" : "Send for approval"}
          </Button>
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
        </div>
      </form>
    </Card>
  );
}

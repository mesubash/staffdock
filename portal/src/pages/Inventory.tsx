import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Card, Empty, ErrorText, Page, Skeleton, selectClass } from "@/components/common";
import { useToast } from "@/components/toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { call, getList, type Tasks } from "@/lib/api";
import { cn } from "@/lib/utils";
import { RequestTable } from "@/pages/Requests";

const TABS = ["Requests", "Assets", "Stock"] as const;
type Tab = (typeof TABS)[number];

export function Inventory() {
  const [tab, setTab] = useState<Tab>("Requests");
  return (
    <Page title="Inventory">
      <div className="flex gap-1 rounded-lg bg-muted p-1 self-start">
        {TABS.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={cn(
              "cursor-pointer rounded-md px-4 py-1.5 text-sm",
              tab === t ? "bg-card font-medium shadow-sm" : "text-muted-foreground",
            )}
          >
            {t}
          </button>
        ))}
      </div>
      {tab === "Requests" ? <RequestQueues /> : tab === "Assets" ? <AssetRegister /> : <Stock />}
    </Page>
  );
}

function RequestQueues() {
  const tasks = useQuery({ queryKey: ["tasks"], queryFn: () => call<Tasks>("staffdock.api.my_tasks") });
  const review = tasks.data?.to_review ?? [];
  const issue = tasks.data?.to_issue ?? [];
  return (
    <>
      <ErrorText error={tasks.error} />
      {tasks.isLoading ? <Skeleton /> : null}
      {tasks.data && !review.length && !issue.length ? (
        <Card>
          <Empty>Nothing to review or issue.</Empty>
        </Card>
      ) : null}
      {review.length ? (
        <Card title="To review">
          <RequestTable rows={review} showRequester />
        </Card>
      ) : null}
      {issue.length ? (
        <Card title="Approved, ready to issue">
          <RequestTable rows={issue} showRequester />
        </Card>
      ) : null}
    </>
  );
}

type Asset = { name: string; asset_name: string; custodian: string | null; location: string; status: string };
type Employee = { name: string; employee_name: string; department: string };
const CONDITIONS = ["Good", "Minor Wear", "Damaged", "Needs Repair", "Lost", "Retired"];

function AssetRegister() {
  const queryClient = useQueryClient();
  const assets = useQuery({
    queryKey: ["assets", "all"],
    queryFn: () =>
      getList<Asset>("Asset", {
        fields: ["name", "asset_name", "custodian", "location", "status"],
        filters: { docstatus: 1 },
        orderBy: "asset_name asc",
        limit: 500,
      }),
  });
  const employees = useQuery({ queryKey: ["employees"], queryFn: () => call<Employee[]>("staffdock.api.employees") });
  const names = Object.fromEntries((employees.data ?? []).map((e) => [e.name, e.employee_name]));
  const [choice, setChoice] = useState<Record<string, string>>({});

  const toast = useToast();
  const done = (message: string) => {
    queryClient.invalidateQueries();
    toast(message);
  };
  const issue = useMutation({
    mutationFn: (a: Asset) => call("staffdock.api.issue_asset", { asset: a.name, employee: choice[a.name] }),
    onSuccess: (_, a) => done(`${a.asset_name} issued to ${names[choice[a.name]] ?? "employee"}`),
  });
  const receive = useMutation({
    mutationFn: (a: Asset) => call("staffdock.api.receive_asset", { asset: a.name, condition: choice[a.name] }),
    onSuccess: (_, a) => done(`${a.asset_name} received back`),
  });

  return (
    <Card title="Asset register">
      <ErrorText error={assets.error ?? issue.error ?? receive.error} />
      {assets.isLoading ? <Skeleton /> : null}
      {assets.data?.length === 0 ? <Empty>No assets yet.</Empty> : null}
      <ul className="divide-y divide-border">
        {assets.data?.map((a) => (
          <li key={a.name} className="flex flex-wrap items-center gap-3 py-3">
            <div className="min-w-48 flex-1">
              <p className="text-sm font-medium">{a.asset_name}</p>
              <p className="text-sm text-muted-foreground">
                {a.name} · {a.custodian ? `With ${names[a.custodian] ?? a.custodian}` : `In store (${a.location})`}
              </p>
            </div>
            {a.custodian ? (
              <>
                <select
                  aria-label={`Condition of ${a.asset_name}`}
                  className={cn(selectClass, "w-40")}
                  value={choice[a.name] ?? ""}
                  onChange={(e) => setChoice({ ...choice, [a.name]: e.target.value })}
                >
                  <option value="">Condition…</option>
                  {CONDITIONS.map((c) => (
                    <option key={c}>{c}</option>
                  ))}
                </select>
                <Button size="sm" variant="outline" disabled={!choice[a.name] || receive.isPending} onClick={() => receive.mutate(a)}>
                  Receive back
                </Button>
              </>
            ) : (
              <>
                <select
                  aria-label={`Issue ${a.asset_name} to`}
                  className={cn(selectClass, "w-48")}
                  value={choice[a.name] ?? ""}
                  onChange={(e) => setChoice({ ...choice, [a.name]: e.target.value })}
                >
                  <option value="">Issue to…</option>
                  {employees.data?.map((e) => (
                    <option key={e.name} value={e.name}>
                      {e.employee_name}
                    </option>
                  ))}
                </select>
                <Button size="sm" disabled={!choice[a.name] || issue.isPending} onClick={() => issue.mutate(a)}>
                  Issue
                </Button>
              </>
            )}
          </li>
        ))}
      </ul>
    </Card>
  );
}

type Bin = { item_code: string; item_name: string; warehouse: string; actual_qty: number; reserved_qty: number };

function Stock() {
  const queryClient = useQueryClient();
  const levels = useQuery({ queryKey: ["stock"], queryFn: () => call<Bin[]>("staffdock.api.stock_levels") });
  const items = useQuery({
    queryKey: ["items"],
    queryFn: () =>
      getList<{ name: string; item_name: string }>("Item", {
        fields: ["name", "item_name"],
        filters: { disabled: 0, is_stock_item: 1 },
        orderBy: "item_name asc",
        limit: 500,
      }),
  });
  const toast = useToast();
  const [form, setForm] = useState({ item_code: "", qty: "", rate: "" });
  const receive = useMutation({
    mutationFn: () => call("staffdock.api.receive_stock", { item_code: form.item_code, qty: form.qty, rate: form.rate || 0 }),
    onSuccess: () => {
      setForm({ item_code: "", qty: "", rate: "" });
      queryClient.invalidateQueries({ queryKey: ["stock"] });
      toast("Stock received");
    },
  });

  return (
    <>
      <Card title="Stock in stores">
        <ErrorText error={levels.error} />
        {levels.isLoading ? <Skeleton /> : null}
        {levels.data?.length === 0 ? <Empty>No stock yet.</Empty> : null}
        <table className="w-full text-sm">
          <thead className="text-left text-muted-foreground">
            <tr>
              <th className="pb-2 font-normal">Item</th>
              <th className="pb-2 font-normal">Store</th>
              <th className="pb-2 text-right font-normal">In stock</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {levels.data?.map((b) => (
              <tr key={`${b.item_code}-${b.warehouse}`}>
                <td className="py-2">{b.item_name}</td>
                <td className="py-2 text-muted-foreground">{b.warehouse}</td>
                <td className={cn("py-2 text-right font-medium", b.actual_qty <= 0 && "text-destructive")}>{b.actual_qty}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <Card title="Receive stock">
        <form
          className="grid gap-4 sm:grid-cols-[1fr_120px_140px_auto] sm:items-end"
          onSubmit={(e) => {
            e.preventDefault();
            receive.mutate();
          }}
        >
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="rcv-item">Item</Label>
            <select
              id="rcv-item"
              className={selectClass}
              value={form.item_code}
              onChange={(e) => setForm({ ...form, item_code: e.target.value })}
            >
              <option value="">Choose an item…</option>
              {items.data?.map((i) => (
                <option key={i.name} value={i.name}>
                  {i.item_name}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="rcv-qty">Quantity</Label>
            <Input id="rcv-qty" type="number" min="1" value={form.qty} onChange={(e) => setForm({ ...form, qty: e.target.value })} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="rcv-rate">Unit cost (NPR)</Label>
            <Input id="rcv-rate" type="number" min="0" value={form.rate} onChange={(e) => setForm({ ...form, rate: e.target.value })} />
          </div>
          <Button type="submit" disabled={!form.item_code || !(Number(form.qty) > 0) || receive.isPending}>
            Receive
          </Button>
        </form>
        <div className="mt-3">
          <ErrorText error={receive.error} />
        </div>
      </Card>
    </>
  );
}

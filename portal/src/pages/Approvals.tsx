import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Card, ConfirmButton, Empty, ErrorText, Page, Skeleton } from "@/components/common";
import { useToast } from "@/components/toast";
import { Button } from "@/components/ui/button";
import { call, getList, type RequestRow } from "@/lib/api";
import { useMe } from "@/lib/session";
import { type Claim, ClaimLines, money } from "@/pages/Expenses";
import { type LeaveRow, leaveDates } from "@/pages/Leave";
import { RequestTable } from "@/pages/Requests";

const FIELDS = ["name", "sd_employee_name", "sd_reason", "workflow_state", "status", "modified"];

export function Approvals() {
  const me = useMe();
  const queryClient = useQueryClient();
  const on = me.features;
  const leaves = useQuery({
    queryKey: ["leaves-to-approve"],
    queryFn: () => (on.leave ? call<LeaveRow[]>("staffdock.api.leaves_to_approve") : Promise.resolve([])),
  });
  const requests = useQuery({
    queryKey: ["approvals", "waiting"],
    queryFn: () =>
      !on.inventory ? Promise.resolve([] as RequestRow[]) : getList<RequestRow>("Material Request", {
        fields: FIELDS,
        filters: { sd_approver: me.user, workflow_state: "Pending Manager Approval" },
      }),
  });
  const history = useQuery({
    queryKey: ["approvals", "history"],
    queryFn: () =>
      !on.inventory ? Promise.resolve([] as RequestRow[]) : getList<RequestRow>("Material Request", {
        fields: FIELDS,
        filters: [
          ["sd_approver", "=", me.user],
          ["workflow_state", "not in", ["Draft", "Pending Manager Approval"]],
        ],
        limit: 10,
      }),
  });
  const toast = useToast();
  const decide = useMutation({
    mutationFn: ({ name, approve }: { name: string; approve: boolean }) =>
      call("staffdock.api.decide_leave", { name, approve: approve ? 1 : 0 }),
    onSuccess: (_, { approve }) => {
      queryClient.invalidateQueries();
      toast(approve ? "Leave approved" : "Leave rejected");
    },
  });

  const expenses = useQuery({
    queryKey: ["expenses-to-approve"],
    queryFn: () => (on.expenses ? call<Claim[]>("staffdock.api.expenses_to_approve") : Promise.resolve([])),
  });
  const decideExpense = useMutation({
    mutationFn: ({ name, approve }: { name: string; approve: boolean }) =>
      call("staffdock.api.decide_expense", { name, approve: approve ? 1 : 0 }),
    onSuccess: (_, { approve }) => {
      queryClient.invalidateQueries();
      toast(approve ? "Claim approved" : "Claim rejected");
    },
  });

  const loaded = leaves.data && requests.data && expenses.data;
  const nothing = loaded && !leaves.data.length && !requests.data.length && !expenses.data.length;

  return (
    <Page title="Approvals">
      <ErrorText error={leaves.error ?? requests.error ?? expenses.error ?? decide.error ?? decideExpense.error} />
      {!loaded && !leaves.error && !requests.error && !expenses.error ? <Skeleton /> : null}
      {nothing ? (
        <Card>
          <Empty>Nothing waiting for your approval.</Empty>
        </Card>
      ) : null}

      {leaves.data?.length ? (
        <Card title="Leave">
          <ul className="divide-y divide-border">
            {leaves.data.map((l) => (
              <li key={l.name} className="flex flex-wrap items-center gap-3 py-3">
                <div className="min-w-48 flex-1">
                  <p className="text-sm font-medium">
                    {l.employee_name} · {l.leave_type}
                  </p>
                  <p className="text-sm text-muted-foreground">{leaveDates(l)}</p>
                  {l.description ? <p className="text-sm text-muted-foreground">{l.description}</p> : null}
                </div>
                <Button size="sm" disabled={decide.isPending} onClick={() => decide.mutate({ name: l.name, approve: true })}>
                  Approve
                </Button>
                <ConfirmButton size="sm" confirmLabel="Click again to reject" disabled={decide.isPending} onConfirm={() => decide.mutate({ name: l.name, approve: false })}>
                  Reject
                </ConfirmButton>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      {expenses.data?.length ? (
        <Card title="Expenses">
          <ul className="divide-y divide-border">
            {expenses.data.map((c) => (
              <li key={c.name} className="py-3">
                <div className="flex flex-wrap items-center gap-3">
                  <div className="min-w-48 flex-1">
                    <p className="text-sm font-medium">
                      {c.employee_name} · {money(c.total_claimed_amount, c.currency)}
                    </p>
                    {c.remark ? <p className="text-sm text-muted-foreground">{c.remark}</p> : null}
                  </div>
                  <Button size="sm" disabled={decideExpense.isPending} onClick={() => decideExpense.mutate({ name: c.name, approve: true })}>
                    Approve
                  </Button>
                  <ConfirmButton size="sm" confirmLabel="Click again to reject" disabled={decideExpense.isPending} onConfirm={() => decideExpense.mutate({ name: c.name, approve: false })}>
                    Reject
                  </ConfirmButton>
                </div>
                <ClaimLines claim={c} />
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      {requests.data?.length ? (
        <Card title="Requests">
          <RequestTable rows={requests.data} showRequester />
        </Card>
      ) : null}

      {history.data?.length ? (
        <Card title="Recently decided">
          <RequestTable rows={history.data} showRequester />
        </Card>
      ) : null}
    </Page>
  );
}

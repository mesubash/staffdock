import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Card, Empty, ErrorText, Page } from "@/components/common";
import { Button } from "@/components/ui/button";
import { call, getList, type RequestRow } from "@/lib/api";
import { useMe } from "@/lib/session";
import { type LeaveRow, leaveDates } from "@/pages/Leave";
import { RequestTable } from "@/pages/Requests";

const FIELDS = ["name", "sd_employee_name", "sd_reason", "workflow_state", "status", "modified"];

export function Approvals() {
  const me = useMe();
  const waiting = useQuery({
    queryKey: ["approvals", "waiting"],
    queryFn: () =>
      getList<RequestRow>("Material Request", {
        fields: FIELDS,
        filters: { sd_approver: me.user, workflow_state: "Pending Manager Approval" },
      }),
  });
  const history = useQuery({
    queryKey: ["approvals", "history"],
    queryFn: () =>
      getList<RequestRow>("Material Request", {
        fields: FIELDS,
        filters: [
          ["sd_approver", "=", me.user],
          ["workflow_state", "not in", ["Draft", "Pending Manager Approval"]],
        ],
        limit: 20,
      }),
  });

  return (
    <Page title="Team approvals">
      <LeaveApprovals />
      <Card title="Requests waiting for you">
        <ErrorText error={waiting.error} />
        {waiting.data?.length === 0 ? <Empty>No requests waiting for your approval.</Empty> : null}
        <RequestTable rows={waiting.data ?? []} showRequester />
      </Card>
      <Card title="Recently decided">
        {history.data?.length === 0 ? <Empty>Nothing yet.</Empty> : null}
        <RequestTable rows={history.data ?? []} showRequester />
      </Card>
    </Page>
  );
}

function LeaveApprovals() {
  const queryClient = useQueryClient();
  const leaves = useQuery({ queryKey: ["leaves-to-approve"], queryFn: () => call<LeaveRow[]>("staffdock.api.leaves_to_approve") });
  const decide = useMutation({
    mutationFn: ({ name, approve }: { name: string; approve: boolean }) => call("staffdock.api.decide_leave", { name, approve: approve ? 1 : 0 }),
    onSuccess: () => queryClient.invalidateQueries(),
  });
  return (
    <Card title="Leave waiting for you">
      <ErrorText error={leaves.error ?? decide.error} />
      {leaves.data?.length === 0 ? <Empty>No leave applications waiting for you.</Empty> : null}
      <ul className="divide-y divide-border">
        {leaves.data?.map((l) => (
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
            <Button size="sm" variant="destructive" disabled={decide.isPending} onClick={() => decide.mutate({ name: l.name, approve: false })}>
              Reject
            </Button>
          </li>
        ))}
      </ul>
    </Card>
  );
}

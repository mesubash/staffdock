import { useQuery } from "@tanstack/react-query";

import { Card, Empty, ErrorText, Page } from "@/components/common";
import { getList, type RequestRow } from "@/lib/api";
import { useMe } from "@/lib/session";
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
      <Card title="Waiting for you">
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

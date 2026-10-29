import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Card, Empty, ErrorText, Page, formatDate } from "@/components/common";
import { Button } from "@/components/ui/button";
import { applyAction, call, getDoc, getList, type Tasks } from "@/lib/api";
import { useMe } from "@/lib/session";

type AssetRow = { name: string; asset_name: string; item_name: string; status: string; modified: string };

export function MyAssets() {
  const me = useMe();
  const queryClient = useQueryClient();
  const assets = useQuery({
    queryKey: ["assets", "mine"],
    queryFn: () =>
      getList<AssetRow>("Asset", {
        fields: ["name", "asset_name", "item_name", "status", "modified"],
        filters: { custodian: me.employee?.name ?? "" },
      }),
    enabled: !!me.employee,
  });
  const tasks = useQuery({ queryKey: ["tasks"], queryFn: () => call<Tasks>("staffdock.api.my_tasks") });
  const acknowledge = useMutation({
    mutationFn: async (movement: string) => applyAction(await getDoc("Asset Movement", movement), "Acknowledge Receipt"),
    onSuccess: () => queryClient.invalidateQueries(),
  });

  const pending = tasks.data?.assets_to_acknowledge ?? [];

  return (
    <Page title="My assets">
      {pending.length ? (
        <Card title="Please confirm you received these">
          <ErrorText error={acknowledge.error} />
          <ul className="divide-y divide-border">
            {pending.map((p) => (
              <li key={p.name} className="flex items-center gap-3 py-3">
                <div className="flex-1">
                  <p className="text-sm font-medium">{p.asset_name}</p>
                  <p className="text-sm text-muted-foreground">{p.asset}</p>
                </div>
                <Button size="sm" disabled={acknowledge.isPending} onClick={() => acknowledge.mutate(p.name)}>
                  I received it
                </Button>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      <Card title="Company property with you">
        <ErrorText error={assets.error} />
        {!me.employee ? <Empty>Your account is not linked to an employee record. Contact HR.</Empty> : null}
        {assets.data?.length === 0 ? <Empty>No company assets are assigned to you.</Empty> : null}
        <ul className="divide-y divide-border">
          {assets.data?.map((a) => (
            <li key={a.name} className="flex items-center gap-3 py-3">
              <div className="flex-1">
                <p className="text-sm font-medium">{a.asset_name}</p>
                <p className="text-sm text-muted-foreground">{a.name}</p>
              </div>
              <span className="text-xs text-muted-foreground">since {formatDate(a.modified)}</span>
            </li>
          ))}
        </ul>
      </Card>
    </Page>
  );
}

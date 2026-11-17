import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown } from "lucide-react";
import { useState } from "react";

import { Card, Empty, ErrorText, Page, Skeleton, formatDate } from "@/components/common";
import { useToast } from "@/components/toast";
import { Button } from "@/components/ui/button";
import { call } from "@/lib/api";
import { cn } from "@/lib/utils";

type Policy = {
  name: string;
  title: string;
  version: string;
  effective_from?: string;
  requires_acknowledgement: number;
  content: string;
  acknowledged: boolean;
};

export function Policies() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const policies = useQuery({ queryKey: ["policies"], queryFn: () => call<Policy[]>("staffdock.api.policies") });
  const [open, setOpen] = useState<string | null>(null);
  const ack = useMutation({
    mutationFn: (name: string) => call("staffdock.api.acknowledge_policy", { name }),
    onSuccess: () => {
      queryClient.invalidateQueries();
      toast("Thanks, acknowledged");
    },
  });

  return (
    <Page title="Policies">
      <ErrorText error={policies.error ?? ack.error} />
      {policies.isLoading ? <Skeleton /> : null}
      {policies.data?.length === 0 ? (
        <Card>
          <Empty>No policies published yet.</Empty>
        </Card>
      ) : null}
      {policies.data?.map((p) => {
        const needsAck = p.requires_acknowledgement && !p.acknowledged;
        const expanded = open === p.name || (open === null && needsAck);
        return (
          <section key={p.name} className="rounded-xl border border-border bg-card">
            <button
              type="button"
              aria-expanded={!!expanded}
              onClick={() => setOpen(expanded ? "" : p.name)}
              className="flex w-full cursor-pointer items-center gap-3 px-4 py-3 text-left"
            >
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold">{p.title}</p>
                <p className="text-xs text-muted-foreground">
                  Version {p.version}
                  {p.effective_from ? ` · effective ${formatDate(p.effective_from)}` : ""}
                </p>
              </div>
              {p.requires_acknowledgement ? (
                <span
                  className={cn(
                    "rounded-full px-2 py-0.5 text-xs font-medium",
                    p.acknowledged ? "bg-green-100 text-green-800" : "bg-amber-100 text-amber-800",
                  )}
                >
                  {p.acknowledged ? "Acknowledged" : "To acknowledge"}
                </span>
              ) : null}
              <ChevronDown className={cn("size-4 text-muted-foreground transition-transform", expanded && "rotate-180")} />
            </button>
            {expanded ? (
              <div className="border-t border-border px-4 py-4">
                <div className="rich text-sm" dangerouslySetInnerHTML={{ __html: p.content }} />
                {needsAck ? (
                  <Button className="mt-4" disabled={ack.isPending} onClick={() => ack.mutate(p.name)}>
                    I have read and agree
                  </Button>
                ) : null}
              </div>
            ) : null}
          </section>
        );
      })}
    </Page>
  );
}

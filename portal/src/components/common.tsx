import { type ReactNode, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { BRAND } from "@/lib/api";
import { cn } from "@/lib/utils";

export function Page({ title, actions, children }: { title: string; actions?: ReactNode; children: ReactNode }) {
  useEffect(() => {
    document.title = `${title} · ${BRAND.title}`;
  }, [title]);
  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6 sm:py-8">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {actions}
      </div>
      <div className="flex flex-col gap-6">{children}</div>
    </div>
  );
}

export function Card({ title, children, className }: { title?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={cn("rounded-xl border border-border bg-card shadow-[0_1px_2px_rgb(0_0_0/0.04)]", className)}>
      {title ? <h2 className="border-b border-border px-4 py-3 text-sm font-semibold">{title}</h2> : null}
      <div className="p-4">{children}</div>
    </section>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="py-6 text-center text-sm text-muted-foreground">{children}</p>;
}

export function ErrorText({ error }: { error: unknown }) {
  if (!error) return null;
  return (
    <p role="alert" className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
      {error instanceof Error ? error.message : String(error)}
    </p>
  );
}

// Workflow states in plain words, with a badge color. Unknown states fall back to their raw name.
const STATES: Record<string, { label: string; tone: string }> = {
  Draft: { label: "Draft", tone: "bg-muted text-muted-foreground" },
  "Pending Manager Approval": { label: "With manager", tone: "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300" },
  "Pending Inventory Review": { label: "With inventory", tone: "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300" },
  "Pending Acknowledgement": { label: "To confirm", tone: "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300" },
  Approved: { label: "Approved", tone: "bg-blue-100 text-blue-800 dark:bg-blue-500/15 dark:text-blue-300" },
  Issued: { label: "Issued", tone: "bg-blue-100 text-blue-800 dark:bg-blue-500/15 dark:text-blue-300" },
  Completed: { label: "Received", tone: "bg-green-100 text-green-800 dark:bg-green-500/15 dark:text-green-300" },
  Acknowledged: { label: "Confirmed", tone: "bg-green-100 text-green-800 dark:bg-green-500/15 dark:text-green-300" },
  "Manager Rejected": { label: "Rejected", tone: "bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300" },
  "Inventory Rejected": { label: "Rejected", tone: "bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300" },
  Closed: { label: "Closed", tone: "bg-muted text-muted-foreground" },
};

function stateKey(state: string, status?: string) {
  return state === "Approved" && status === "Issued" ? "Issued" : state;
}

export function stateLabel(state: string, status?: string) {
  const key = stateKey(state, status);
  return STATES[key]?.label ?? key;
}

export function StatusBadge({ state, status }: { state: string; status?: string }) {
  const key = stateKey(state, status);
  return (
    <span className={cn("inline-flex rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap", STATES[key]?.tone ?? "bg-muted")}>
      {stateLabel(state, status)}
    </span>
  );
}

/** What a history entry means, from the state a request moved into. */
export const HISTORY_LABELS: Record<string, string> = {
  "Pending Manager Approval": "Sent for approval",
  "Pending Inventory Review": "Approved by manager",
  Approved: "Approved by inventory",
  "Manager Rejected": "Rejected by manager",
  "Inventory Rejected": "Rejected by inventory",
  Completed: "Receipt confirmed",
  Closed: "Closed by inventory",
};

/** Button text for workflow actions. */
export const ACTION_LABELS: Record<string, string> = {
  Submit: "Send for approval",
  "Acknowledge Receipt": "I received the items",
  Close: "Close request",
};

export function formatDate(value?: string) {
  if (!value) return "";
  return new Date(value.replace(" ", "T")).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

export const selectClass =
  "flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring";

/** Grey placeholder rows while a list loads. */
export function Skeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div aria-busy="true" aria-label="Loading" className="flex flex-col gap-3 py-2">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="h-10 animate-pulse rounded-md bg-muted" />
      ))}
    </div>
  );
}

/** Destructive action that needs a second click: "Reject" becomes "Click again to reject" for 5 seconds. */
export function ConfirmButton({
  children,
  confirmLabel,
  onConfirm,
  disabled,
  variant = "destructive",
  size = "default",
}: {
  children: ReactNode;
  confirmLabel: string;
  onConfirm: () => void;
  disabled?: boolean;
  variant?: "destructive" | "ghost" | "outline";
  size?: "default" | "sm";
}) {
  const [armed, setArmed] = useState(false);
  useEffect(() => {
    if (!armed) return;
    const t = setTimeout(() => setArmed(false), 5000);
    return () => clearTimeout(t);
  }, [armed]);
  return (
    <Button
      type="button"
      size={size}
      variant={armed ? "destructive" : variant}
      disabled={disabled}
      onClick={() => {
        if (armed) {
          setArmed(false);
          onConfirm();
        } else {
          setArmed(true);
        }
      }}
    >
      {armed ? confirmLabel : children}
    </Button>
  );
}

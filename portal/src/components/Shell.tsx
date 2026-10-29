import { Link } from "@tanstack/react-router";
import { LogOut, Settings } from "lucide-react";
import type { ReactNode } from "react";

import { BRAND, logout } from "@/lib/api";
import { useMe } from "@/lib/session";

export function Shell({ children }: { children: ReactNode }) {
  const me = useMe();
  const nav = [
    { to: "/", label: "Home", show: true },
    { to: "/requests", label: "Requests", show: true },
    { to: "/assets", label: "My Assets", show: true },
    { to: "/approvals", label: "Approvals", show: me.is_manager },
    { to: "/inventory", label: "Inventory", show: me.is_inventory },
  ].filter((n) => n.show);

  return (
    <div className="flex min-h-dvh flex-col bg-secondary">
      <header className="border-b border-border bg-card">
        <div className="mx-auto flex max-w-5xl items-center gap-4 px-4 sm:px-6">
          <Link to="/" className="flex items-center gap-2 py-3 font-semibold">
            <img src={BRAND.logo} alt="" className="size-7" />
            <span className="hidden sm:inline">{BRAND.title}</span>
          </Link>
          <nav className="flex flex-1 gap-1 overflow-x-auto">
            {nav.map((n) => (
              <Link
                key={n.to}
                to={n.to}
                activeOptions={{ exact: n.to === "/" }}
                className="rounded-md px-3 py-2 text-sm whitespace-nowrap text-muted-foreground hover:bg-accent hover:text-foreground"
                activeProps={{ className: "bg-accent font-medium text-foreground" }}
              >
                {n.label}
              </Link>
            ))}
          </nav>
          {me.has_desk ? (
            <a href="/desk" title="Admin console" className="rounded-md p-2 text-muted-foreground hover:bg-accent">
              <Settings className="size-4" />
            </a>
          ) : null}
          <span className="hidden text-sm text-muted-foreground md:inline">{me.full_name}</span>
          <button
            type="button"
            title="Sign out"
            className="cursor-pointer rounded-md p-2 text-muted-foreground hover:bg-accent"
            onClick={async () => {
              await logout().catch(() => undefined);
              window.location.assign("/login");
            }}
          >
            <LogOut className="size-4" />
          </button>
        </div>
      </header>
      <main className="flex-1">{children}</main>
    </div>
  );
}

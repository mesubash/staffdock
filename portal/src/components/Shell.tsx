import { Link } from "@tanstack/react-router";
import { LogOut, Menu, Settings, X } from "lucide-react";
import { type ReactNode, useState } from "react";

import { BRAND, logout } from "@/lib/api";
import { useMe } from "@/lib/session";
import { Avatar } from "@/pages/Profile";

export function Shell({ children }: { children: ReactNode }) {
  const me = useMe();
  const [menuOpen, setMenuOpen] = useState(false);
  const f = me.features;
  const nav = [
    { to: "/", label: "Home", show: true },
    { to: "/attendance", label: "Attendance", show: f.attendance },
    { to: "/leave", label: "Leave", show: f.leave },
    { to: "/expenses", label: "Expenses", show: f.expenses },
    { to: "/requests", label: "Requests", show: f.inventory },
    { to: "/assets", label: "Assets", show: f.inventory },
    { to: "/people", label: "People", show: f.people },
    { to: "/policies", label: "Policies", show: f.news },
    { to: "/approvals", label: "Approvals", show: (me.is_manager || me.is_approver) && (f.inventory || f.leave || f.expenses) },
    { to: "/inventory", label: "Inventory", show: me.is_inventory && f.inventory },
  ].filter((n) => n.show);

  return (
    <div className="flex min-h-dvh flex-col bg-secondary">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-card focus:px-3 focus:py-2 focus:text-sm">
        Skip to content
      </a>
      <header className="border-b border-border bg-card">
        <div className="mx-auto flex max-w-7xl items-center gap-3 px-4 sm:px-6">
          <Link to="/" className="flex items-center gap-2 py-3 font-semibold">
            <img src={BRAND.logo} alt="" className="size-7" />
            <span className="hidden whitespace-nowrap sm:inline lg:hidden xl:inline">{BRAND.title}</span>
          </Link>
          <nav aria-label="Main" className="hidden flex-1 gap-1 lg:flex">
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
          <div className="flex-1 lg:hidden" />
          <button
            type="button"
            aria-expanded={menuOpen}
            className="flex cursor-pointer items-center gap-1 rounded-md px-2 py-2 text-sm text-muted-foreground hover:bg-accent lg:hidden"
            onClick={() => setMenuOpen(!menuOpen)}
          >
            {menuOpen ? <X className="size-4" /> : <Menu className="size-4" />} Menu
          </button>
          {me.has_desk ? (
            <a href="/desk" title="Admin console" aria-label="Admin console" className="rounded-md p-2 text-muted-foreground hover:bg-accent">
              <Settings className="size-4" />
            </a>
          ) : null}
          {me.employee ? (
            <Link to="/profile" title="My profile" className="flex items-center gap-2 rounded-md px-2 py-1 text-sm text-muted-foreground hover:bg-accent">
              <Avatar name={me.full_name} image={me.image} size="size-7" />
              <span className="hidden whitespace-nowrap 2xl:inline">{me.full_name}</span>
            </Link>
          ) : (
            <span className="hidden text-sm text-muted-foreground md:inline">{me.full_name}</span>
          )}
          <button
            type="button"
            title="Sign out"
            aria-label="Sign out"
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
      {menuOpen ? (
        <nav aria-label="Main" className="border-b border-border bg-card px-4 py-2 lg:hidden">
          {nav.map((n) => (
            <Link
              key={n.to}
              to={n.to}
              onClick={() => setMenuOpen(false)}
              activeOptions={{ exact: n.to === "/" }}
              className="block rounded-md px-3 py-2.5 text-sm text-muted-foreground hover:bg-accent"
              activeProps={{ className: "bg-accent font-medium text-foreground" }}
            >
              {n.label}
            </Link>
          ))}
        </nav>
      ) : null}
      <main id="main" className="flex-1">{children}</main>
    </div>
  );
}

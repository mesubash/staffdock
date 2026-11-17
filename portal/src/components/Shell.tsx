import { Link } from "@tanstack/react-router";
import { LogOut, Menu, Settings, X } from "lucide-react";
import { type ReactNode, useState } from "react";

import { BRAND, logout } from "@/lib/api";
import { useMe } from "@/lib/session";
import { Avatar } from "@/pages/Profile";

export function Shell({ children }: { children: ReactNode }) {
  const me = useMe();
  const [menuOpen, setMenuOpen] = useState(false);
  const nav = [
    { to: "/", label: "Home", show: true },
    { to: "/attendance", label: "Attendance", show: true },
    { to: "/leave", label: "Leave", show: true },
    { to: "/requests", label: "Requests", show: true },
    { to: "/assets", label: "Assets", show: true },
    { to: "/people", label: "People", show: true },
    { to: "/policies", label: "Policies", show: true },
    { to: "/approvals", label: "Approvals", show: me.is_manager || me.is_leave_approver },
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
          <nav className="hidden flex-1 gap-1 lg:flex">
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
            <a href="/desk" title="Admin console" className="rounded-md p-2 text-muted-foreground hover:bg-accent">
              <Settings className="size-4" />
            </a>
          ) : null}
          {me.employee ? (
            <Link to="/profile" title="My profile" className="flex items-center gap-2 rounded-md px-2 py-1 text-sm text-muted-foreground hover:bg-accent">
              <Avatar name={me.full_name} image={me.image} size="size-7" />
              <span className="hidden lg:inline">{me.full_name}</span>
            </Link>
          ) : (
            <span className="hidden text-sm text-muted-foreground md:inline">{me.full_name}</span>
          )}
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
      {menuOpen ? (
        <nav className="border-b border-border bg-card px-4 py-2 lg:hidden">
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
      <main className="flex-1">{children}</main>
    </div>
  );
}

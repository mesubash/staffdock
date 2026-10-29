import { useState } from "react";

import { ErrorText } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { BRAND, login } from "@/lib/api";

export function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  return (
    <div data-theme="light" className="flex min-h-dvh items-center justify-center bg-secondary px-4">
      <form
        className="w-full max-w-sm rounded-xl border border-border bg-card p-8 shadow-[0_1px_2px_rgb(0_0_0/0.04),0_8px_24px_-12px_rgb(0_0_0/0.1)]"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError(null);
          try {
            await login(username, password);
            // Reload so the page picks up the new session's CSRF token.
            window.location.assign(window.location.pathname);
          } catch (err) {
            setError(err);
            setBusy(false);
          }
        }}
      >
        <div className="mb-6 flex items-center gap-2">
          <img src={BRAND.logo} alt="" className="size-8" />
          <span className="text-lg font-semibold">{BRAND.title}</span>
        </div>
        <h1 className="mb-1 text-xl font-semibold">Sign in</h1>
        <p className="mb-6 text-sm text-muted-foreground">Use your company account.</p>

        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="username">{BRAND.email_domain ? "Username" : "Email"}</Label>
            <div className="flex items-center rounded-md border border-input shadow-sm focus-within:ring-1 focus-within:ring-ring">
              <input
                id="username"
                autoFocus
                required
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="h-9 min-w-0 flex-1 bg-transparent px-3 text-sm outline-none"
                placeholder={BRAND.email_domain ? "username" : "you@company.com"}
              />
              {BRAND.email_domain ? <span className="pr-3 text-sm text-muted-foreground">@{BRAND.email_domain}</span> : null}
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          <ErrorText error={error} />
          <Button type="submit" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </Button>
        </div>
      </form>
    </div>
  );
}

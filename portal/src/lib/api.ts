// Thin client for the Frappe REST API. The session cookie authenticates; the CSRF token
// comes from www/staff.html (dev uses ignore_csrf on the local site).

declare global {
  interface Window {
    csrf_token?: string;
    staffdock?: { title: string; logo: string; email_domain: string };
  }
}

/** Branding and sign-in domain from StaffDock Settings (injected by www/staff.html). */
export const BRAND = window.staffdock ?? {
  title: "StaffDock",
  logo: "/assets/staffdock/images/logo.svg",
  email_domain: "",
};

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

function stripHtml(s: string) {
  return s.replace(/<[^>]+>/g, "").trim();
}

function errorMessage(body: Record<string, unknown>): string {
  if (typeof body._server_messages === "string") {
    try {
      const first = JSON.parse(JSON.parse(body._server_messages)[0]);
      if (first?.message) return stripHtml(first.message);
    } catch {
      /* fall through */
    }
  }
  if (typeof body.exception === "string") return body.exception.split(":").slice(1).join(":").trim() || body.exception;
  return "Something went wrong. Please try again.";
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(path, {
    credentials: "include",
    ...init,
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "X-Frappe-CSRF-Token": window.csrf_token ?? "",
      ...init.headers,
    },
  });
  const body = (await res.json().catch(() => ({}))) as Record<string, unknown>;
  if (!res.ok) throw new ApiError(errorMessage(body), res.status);
  return body as T;
}

export async function call<T = unknown>(method: string, args: Record<string, unknown> = {}): Promise<T> {
  const body = await request<{ message: T }>(`/api/method/${method}`, {
    method: "POST",
    body: JSON.stringify(args),
  });
  return body.message;
}

type Filters = Record<string, unknown> | unknown[][];

export async function getList<T>(
  doctype: string,
  opts: { fields?: string[]; filters?: Filters; orderBy?: string; limit?: number } = {},
): Promise<T[]> {
  const q = new URLSearchParams({
    fields: JSON.stringify(opts.fields ?? ["name"]),
    filters: JSON.stringify(opts.filters ?? {}),
    order_by: opts.orderBy ?? "modified desc",
    limit_page_length: String(opts.limit ?? 100),
  });
  const body = await request<{ data: T[] }>(`/api/resource/${encodeURIComponent(doctype)}?${q}`);
  return body.data;
}

export async function getDoc<T>(doctype: string, name: string): Promise<T> {
  const body = await request<{ data: T }>(`/api/resource/${encodeURIComponent(doctype)}/${encodeURIComponent(name)}`);
  return body.data;
}

export async function insert<T>(doctype: string, doc: Record<string, unknown>): Promise<T> {
  const body = await request<{ data: T }>(`/api/resource/${encodeURIComponent(doctype)}`, {
    method: "POST",
    body: JSON.stringify(doc),
  });
  return body.data;
}

// --- Workflow: only the actions the server says this user may take on this document.

export type Transition = { action: string; next_state: string };

export function getActions(doc: unknown) {
  return call<Transition[]>("frappe.model.workflow.get_transitions", { doc });
}

export function applyAction(doc: unknown, action: string) {
  return call("frappe.model.workflow.apply_workflow", { doc, action });
}

// --- Session

export async function login(username: string, password: string) {
  const name = username.trim();
  const usr = name.includes("@") || !BRAND.email_domain ? name : `${name}@${BRAND.email_domain}`;
  await request("/api/method/login", { method: "POST", body: JSON.stringify({ usr, pwd: password }) });
}

export async function logout() {
  await request("/api/method/logout", { method: "POST" });
}

// --- Shapes used by the portal

export type Me = {
  user: string;
  full_name: string;
  employee: { name: string; employee_name: string; department: string } | null;
  is_manager: boolean;
  is_inventory: boolean;
  has_desk: boolean;
  default_warehouse: string;
};

export type RequestRow = {
  name: string;
  sd_employee_name?: string;
  sd_reason?: string;
  workflow_state: string;
  status: string;
  modified: string;
};

export type Tasks = {
  to_approve: RequestRow[];
  requests_to_acknowledge: RequestRow[];
  assets_to_acknowledge: { name: string; asset: string; asset_name: string; modified: string }[];
  open_requests: number;
  my_assets: number;
  to_review?: RequestRow[];
  to_issue?: RequestRow[];
};

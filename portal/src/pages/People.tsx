import { useQuery } from "@tanstack/react-query";
import { Mail, Search } from "lucide-react";
import { useState } from "react";

import { Card, Empty, ErrorText, Page, Skeleton, formatDate } from "@/components/common";
import { call } from "@/lib/api";
import { Avatar } from "@/pages/Profile";

type Person = { name: string; employee_name: string; designation?: string; department?: string; company_email?: string; image?: string };
type PeopleData = {
  employees: Person[];
  out_today: { employee_name: string; image?: string; back_after: string }[];
  holidays: { holiday_date: string; description: string }[];
};

export function People() {
  const data = useQuery({ queryKey: ["people"], queryFn: () => call<PeopleData>("staffdock.api.people") });
  const [query, setQuery] = useState("");
  const d = data.data;
  const q = query.trim().toLowerCase();
  const shown = d?.employees.filter((e) =>
    [e.employee_name, e.designation, e.department, e.company_email].some((v) => v?.toLowerCase().includes(q)),
  );

  return (
    <Page title="People">
      <ErrorText error={data.error} />
      {!d && !data.error ? <Skeleton rows={4} /> : null}
      {d ? (
        <div className="grid gap-6 sm:grid-cols-2">
          <Card title="Out today">
            {d.out_today.length ? (
              <ul className="flex flex-col gap-3">
                {d.out_today.map((o) => (
                  <li key={o.employee_name} className="flex items-center gap-3 text-sm">
                    <Avatar name={o.employee_name} image={o.image} size="size-8" />
                    <span className="flex-1 font-medium">{o.employee_name}</span>
                    <span className="text-muted-foreground">back after {formatDate(o.back_after)}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <Empty>Everyone is in today.</Empty>
            )}
          </Card>
          <Card title="Upcoming holidays">
            {d.holidays.length ? (
              <ul className="flex flex-col gap-3">
                {d.holidays.map((h) => (
                  <li key={h.holiday_date} className="flex items-center justify-between gap-3 text-sm">
                    <span className="font-medium">{h.description}</span>
                    <span className="text-muted-foreground">{formatDate(h.holiday_date)}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <Empty>No upcoming holidays.</Empty>
            )}
          </Card>
        </div>
      ) : null}

      {d ? (
        <Card title={`Directory (${d.employees.length})`}>
          <div className="mb-3 flex items-center gap-2 rounded-md border border-input px-3 shadow-sm focus-within:ring-1 focus-within:ring-ring">
            <Search className="size-4 text-muted-foreground" />
            <input
              aria-label="Search people"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search by name, role or department"
              className="h-9 flex-1 bg-transparent text-sm outline-none"
            />
          </div>
          {shown?.length === 0 ? <Empty>No one matches “{query}”.</Empty> : null}
          <ul className="divide-y divide-border">
            {shown?.map((e) => (
              <li key={e.name} className="flex items-center gap-3 py-3">
                <Avatar name={e.employee_name} image={e.image} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">{e.employee_name}</p>
                  <p className="truncate text-sm text-muted-foreground">{[e.designation, e.department].filter(Boolean).join(" · ")}</p>
                </div>
                {e.company_email ? (
                  <a href={`mailto:${e.company_email}`} title={e.company_email} className="rounded-md p-2 text-muted-foreground hover:bg-accent">
                    <Mail className="size-4" />
                    <span className="sr-only">Email {e.employee_name}</span>
                  </a>
                ) : null}
              </li>
            ))}
          </ul>
        </Card>
      ) : null}
    </Page>
  );
}

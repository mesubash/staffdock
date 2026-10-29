import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Card, Empty, ErrorText, Page, formatDate } from "@/components/common";
import { Button } from "@/components/ui/button";
import { call } from "@/lib/api";

type Today = {
  checked_in: boolean;
  first_in: string | null;
  last: string | null;
  worked_seconds: number;
  geolocation_required: boolean;
};

type Day = { date: string; first_in: string | null; last_out: string | null; worked_seconds: number };

export function hours(seconds: number) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return h ? `${h}h ${m}m` : `${m}m`;
}

function time(value: string | null) {
  if (!value) return "—";
  return new Date(value.replace(" ", "T")).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

function position(): Promise<{ latitude?: number; longitude?: number }> {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) return reject(new Error("This browser can't share your location."));
    navigator.geolocation.getCurrentPosition(
      (p) => resolve({ latitude: p.coords.latitude, longitude: p.coords.longitude }),
      () => reject(new Error("Allow location access to check in.")),
      { timeout: 10000 },
    );
  });
}

/** Check-in card used on Home and the Attendance page. */
export function CheckInCard() {
  const queryClient = useQueryClient();
  const today = useQuery({ queryKey: ["attendance", "today"], queryFn: () => call<Today>("staffdock.api.attendance_today") });
  const toggle = useMutation({
    mutationFn: async () => call("staffdock.api.check_in_out", today.data?.geolocation_required ? await position() : {}),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["attendance"] }),
  });
  const t = today.data;

  return (
    <Card title="Attendance">
      <ErrorText error={today.error ?? toggle.error} />
      {t ? (
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex-1">
            <p className="text-sm font-medium">
              {t.checked_in ? `Checked in at ${time(t.first_in)}` : t.last ? `Checked out at ${time(t.last)}` : "Not checked in today"}
            </p>
            <p className="text-sm text-muted-foreground">{hours(t.worked_seconds)} today</p>
          </div>
          <Button variant={t.checked_in ? "outline" : "default"} disabled={toggle.isPending} onClick={() => toggle.mutate()}>
            {t.checked_in ? "Check out" : "Check in"}
          </Button>
        </div>
      ) : null}
    </Card>
  );
}

export function Attendance() {
  const history = useQuery({ queryKey: ["attendance", "history"], queryFn: () => call<Day[]>("staffdock.api.attendance_history") });
  return (
    <Page title="Attendance">
      <CheckInCard />
      <Card title="Last 30 days">
        <ErrorText error={history.error} />
        {history.data?.length === 0 ? <Empty>No check-ins yet.</Empty> : null}
        {history.data?.length ? (
          <table className="w-full text-sm">
            <thead className="text-left text-muted-foreground">
              <tr>
                <th className="pb-2 font-normal">Day</th>
                <th className="pb-2 font-normal">In</th>
                <th className="pb-2 font-normal">Out</th>
                <th className="pb-2 text-right font-normal">Worked</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {history.data.map((d) => (
                <tr key={d.date}>
                  <td className="py-2">{formatDate(d.date)}</td>
                  <td className="py-2">{time(d.first_in)}</td>
                  <td className="py-2">{time(d.last_out)}</td>
                  <td className="py-2 text-right font-medium">{hours(d.worked_seconds)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
      </Card>
    </Page>
  );
}

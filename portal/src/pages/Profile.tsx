import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Camera, FileText } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Card, ErrorText, Page, Skeleton, formatDate } from "@/components/common";
import { useToast } from "@/components/toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { call, uploadFile } from "@/lib/api";

type Profile = {
  employee_name: string;
  designation?: string;
  department?: string;
  company: string;
  date_of_joining?: string;
  company_email?: string;
  image?: string;
  manager?: string;
  cell_number?: string;
  personal_email?: string;
  current_address?: string;
  person_to_be_contacted?: string;
  emergency_phone_number?: string;
  relation?: string;
};

const EDITABLE = [
  "cell_number",
  "personal_email",
  "current_address",
  "person_to_be_contacted",
  "emergency_phone_number",
  "relation",
] as const;
type Editable = Record<(typeof EDITABLE)[number], string>;

export function Avatar({ name, image, size = "size-10" }: { name: string; image?: string | null; size?: string }) {
  const initials = name
    .split(" ")
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
  return image ? (
    <img src={image} alt="" className={`${size} shrink-0 rounded-full object-cover`} />
  ) : (
    <span aria-hidden className={`${size} grid shrink-0 place-items-center rounded-full bg-muted text-sm font-medium`}>
      {initials}
    </span>
  );
}

export function ProfilePage() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const profile = useQuery({ queryKey: ["profile"], queryFn: () => call<Profile>("staffdock.api.my_profile") });
  const [form, setForm] = useState<Editable | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (profile.data) setForm(Object.fromEntries(EDITABLE.map((k) => [k, profile.data[k] ?? ""])) as Editable);
  }, [profile.data]);

  const save = useMutation({
    mutationFn: () => call<Profile>("staffdock.api.update_profile", form ?? {}),
    onSuccess: (p) => {
      queryClient.setQueryData(["profile"], p);
      toast("Profile saved");
    },
  });
  const photo = useMutation({
    mutationFn: async (file: File) => call("staffdock.api.set_profile_photo", { file_url: await uploadFile(file, false) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["profile"] });
      toast("Photo updated");
    },
  });

  const p = profile.data;
  const field = (key: keyof Editable, label: string, type = "text") => (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={key}>{label}</Label>
      <Input id={key} type={type} value={form?.[key] ?? ""} onChange={(e) => setForm({ ...(form as Editable), [key]: e.target.value })} />
    </div>
  );

  return (
    <Page title="My profile">
      <ErrorText error={profile.error} />
      {!p ? <Skeleton rows={4} /> : null}
      {p ? (
        <Card>
          <div className="flex flex-wrap items-center gap-4">
            <div className="relative">
              <Avatar name={p.employee_name} image={p.image} size="size-16" />
              <button
                type="button"
                aria-label="Change photo"
                className="absolute -right-1 -bottom-1 grid size-7 cursor-pointer place-items-center rounded-full border border-border bg-card shadow-sm hover:bg-accent"
                onClick={() => fileInput.current?.click()}
              >
                <Camera className="size-3.5" />
              </button>
              <input
                ref={fileInput}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) photo.mutate(file);
                  e.target.value = "";
                }}
              />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-lg font-semibold">{p.employee_name}</p>
              <p className="text-sm text-muted-foreground">{[p.designation, p.department].filter(Boolean).join(" · ")}</p>
            </div>
          </div>
          <ErrorText error={photo.error} />
          <dl className="mt-5 grid gap-4 text-sm sm:grid-cols-3">
            <Detail label="Work email" value={p.company_email} />
            <Detail label="Manager" value={p.manager} />
            <Detail label="Joined" value={formatDate(p.date_of_joining)} />
          </dl>
        </Card>
      ) : null}

      <Documents />

      {form ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate();
          }}
          className="flex flex-col gap-6"
        >
          <Card title="Contact details">
            <div className="grid gap-4 sm:grid-cols-2">
              {field("cell_number", "Mobile", "tel")}
              {field("personal_email", "Personal email", "email")}
              <div className="sm:col-span-2">{field("current_address", "Address")}</div>
            </div>
          </Card>
          <Card title="Emergency contact">
            <div className="grid gap-4 sm:grid-cols-3">
              {field("person_to_be_contacted", "Name")}
              {field("relation", "Relation")}
              {field("emergency_phone_number", "Phone", "tel")}
            </div>
          </Card>
          <ErrorText error={save.error} />
          <div>
            <Button type="submit" disabled={save.isPending}>
              {save.isPending ? "Saving…" : "Save"}
            </Button>
          </div>
        </form>
      ) : null}
    </Page>
  );
}

function Detail({ label, value }: { label: string; value?: string }) {
  return (
    <div>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 font-medium">{value || "—"}</dd>
    </div>
  );
}

type Doc = { name: string; file_name: string; file_url: string; file_size: number; creation: string };

function size(bytes: number) {
  return bytes > 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

function Documents() {
  const docs = useQuery({ queryKey: ["documents"], queryFn: () => call<Doc[]>("staffdock.api.my_documents") });
  return (
    <Card title="My documents">
      <ErrorText error={docs.error} />
      {docs.isLoading ? <Skeleton rows={2} /> : null}
      {docs.data?.length === 0 ? <p className="text-sm text-muted-foreground">HR hasn't shared any documents with you yet.</p> : null}
      <ul className="divide-y divide-border">
        {docs.data?.map((d) => (
          <li key={d.name} className="flex items-center gap-3 py-2.5 text-sm">
            <FileText className="size-4 text-muted-foreground" />
            <a href={d.file_url} target="_blank" rel="noreferrer" className="min-w-0 flex-1 truncate font-medium text-primary underline-offset-4 hover:underline">
              {d.file_name}
            </a>
            <span className="text-xs text-muted-foreground">{size(d.file_size)}</span>
            <span className="text-xs text-muted-foreground">{formatDate(d.creation)}</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

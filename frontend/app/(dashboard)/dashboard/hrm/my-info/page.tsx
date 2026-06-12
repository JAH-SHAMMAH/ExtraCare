"use client";

import { useEffect, useState } from "react";
import { Loader2, Save, User, FileText, Phone, Briefcase, Wallet, BadgeCheck, Users2 } from "lucide-react";
import { useMyHrProfile, useUpdateMyHrProfile } from "@/hooks/useHrm";
import type { HRProfile, HRMembership, HRDependent } from "@/types";

type FormState = Partial<HRProfile>;

/**
 * My HRM Info — 7 sections over one scrollable page.
 *
 * Submits only changed fields via PATCH /hr/me. The backend treats omitted
 * keys as "no change" (exclude_unset) and explicit null as "clear this",
 * so we send a diff rather than the full payload.
 */
export default function MyHrmInfoPage() {
  const { data, isLoading } = useMyHrProfile();
  const update = useUpdateMyHrProfile();

  const [form, setForm] = useState<FormState>({});
  const [initial, setInitial] = useState<FormState>({});

  useEffect(() => {
    if (data) {
      const shape: FormState = { ...data };
      setForm(shape);
      setInitial(shape);
    }
  }, [data]);

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) =>
    setForm((f) => ({ ...f, [key]: value }));

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // Only send keys whose value changed, so the backend's exclude_unset
    // semantics apply. Arrays/objects compared by JSON because nested
    // identity changes on every render.
    const payload: Record<string, unknown> = {};
    (Object.keys(form) as (keyof FormState)[]).forEach((k) => {
      const a = form[k];
      const b = initial[k];
      if (JSON.stringify(a) !== JSON.stringify(b)) payload[k as string] = a;
    });
    if (Object.keys(payload).length === 0) return;
    update.mutate(payload);
  };

  if (isLoading || !data) {
    return (
      <div className="p-8 flex items-center gap-2 text-slate-500">
        <Loader2 className="w-4 h-4 animate-spin" /> Loading profile…
      </div>
    );
  }

  return (
    <div className="p-6 lg:p-8 max-w-5xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
          <span>HRM</span><span>/</span>
          <span className="text-brand-600 font-semibold">My Info</span>
        </nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">My HRM Info</h1>
        <p className="text-slate-500 text-sm mt-0.5">
          Your employee record — keep it current. Salary and bank details are visible only to you and HR admins.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <Section icon={User} title="Personal Details">
          <Row>
            <Field label="Title" value={form.title} onChange={(v) => set("title", v)} placeholder="Mr / Mrs / Dr" />
            <Field label="Staff ID" value={form.staff_id} onChange={(v) => set("staff_id", v)} placeholder="EMP-0001" />
            <Field label="Employment Status" value={form.employment_status} onChange={(v) => set("employment_status", v)} placeholder="Active / Contract / Probation" />
          </Row>
          <Row>
            <Field label="First Name" value={form.first_name} onChange={(v) => set("first_name", v)} />
            <Field label="Middle Name" value={form.middle_name} onChange={(v) => set("middle_name", v)} />
            <Field label="Surname" value={form.surname} onChange={(v) => set("surname", v)} />
          </Row>
          <Row>
            <Select
              label="Gender" value={form.gender} onChange={(v) => set("gender", v)}
              options={["Male", "Female", "Other", "Prefer not to say"]}
            />
            <Select
              label="Marital Status" value={form.marital_status} onChange={(v) => set("marital_status", v)}
              options={["Single", "Married", "Divorced", "Widowed"]}
            />
            <Field label="Nationality" value={form.nationality} onChange={(v) => set("nationality", v)} placeholder="Nigerian" />
          </Row>
          <Row>
            <Field label="Date of Birth" type="date" value={form.date_of_birth} onChange={(v) => set("date_of_birth", v)} />
            <div /><div />
          </Row>
        </Section>

        <Section icon={FileText} title="Identification">
          <Row>
            <Field label="National ID Number" value={form.national_id} onChange={(v) => set("national_id", v)} />
            <Field label="National ID Expiry" type="date" value={form.national_id_expiry} onChange={(v) => set("national_id_expiry", v)} />
            <div />
          </Row>
        </Section>

        <Section icon={Phone} title="Contact">
          <Field label="Address" value={form.address} onChange={(v) => set("address", v)} textarea />
          <Row>
            <Field label="Emergency Contact Name" value={form.emergency_contact_name} onChange={(v) => set("emergency_contact_name", v)} />
            <Field label="Emergency Contact Phone" value={form.emergency_contact_phone} onChange={(v) => set("emergency_contact_phone", v)} placeholder="+234…" />
            <Field label="Relationship" value={form.emergency_contact_relationship} onChange={(v) => set("emergency_contact_relationship", v)} placeholder="Spouse / Parent / Sibling" />
          </Row>
        </Section>

        <Section icon={Briefcase} title="Employment">
          <Row>
            <Field label="Department" value={form.department} disabled note="Managed by HR" />
            <Field label="Job Title" value={form.job_title} disabled note="Managed by HR" />
            <Field label="Hire Date" type="date" value={form.hire_date} onChange={(v) => set("hire_date", v)} />
          </Row>
        </Section>

        <Section icon={Wallet} title="Salary & Pension" badge="Private">
          <Row>
            <Field
              label="Salary" type="number" value={form.salary?.toString() ?? ""}
              onChange={(v) => set("salary", v === "" ? null : Number(v))}
            />
            <Field label="Currency" value={form.salary_currency} onChange={(v) => set("salary_currency", v)} placeholder="NGN" />
            <div />
          </Row>
          <Row>
            <Field label="Bank Name" value={form.bank_name} onChange={(v) => set("bank_name", v)} />
            <Field label="Bank Account Name" value={form.bank_account_name} onChange={(v) => set("bank_account_name", v)} />
            <Field label="Bank Account Number" value={form.bank_account_number} onChange={(v) => set("bank_account_number", v)} />
          </Row>
          <Row>
            <Field label="Pension Provider" value={form.pension_provider} onChange={(v) => set("pension_provider", v)} />
            <Field label="Pension ID" value={form.pension_id} onChange={(v) => set("pension_id", v)} />
            <div />
          </Row>
        </Section>

        <Section icon={BadgeCheck} title="Professional Memberships">
          <MembershipEditor
            value={form.memberships ?? []}
            onChange={(list) => set("memberships", list)}
          />
        </Section>

        <Section icon={Users2} title="Family">
          <div className="grid md:grid-cols-2 gap-4">
            <div>
              <p className="text-xs font-bold text-slate-600 uppercase tracking-wide mb-2">Next of Kin</p>
              <Field label="Name" value={form.next_of_kin?.name} onChange={(v) => set("next_of_kin", { ...(form.next_of_kin ?? {}), name: v ?? undefined })} />
              <Field label="Relationship" value={form.next_of_kin?.relationship} onChange={(v) => set("next_of_kin", { ...(form.next_of_kin ?? {}), relationship: v ?? undefined })} />
              <Field label="Phone" value={form.next_of_kin?.phone} onChange={(v) => set("next_of_kin", { ...(form.next_of_kin ?? {}), phone: v ?? undefined })} />
              <Field label="Email" value={form.next_of_kin?.email} onChange={(v) => set("next_of_kin", { ...(form.next_of_kin ?? {}), email: v ?? undefined })} />
            </div>
            <div>
              <p className="text-xs font-bold text-slate-600 uppercase tracking-wide mb-2">Dependents</p>
              <DependentsEditor
                value={form.dependents ?? []}
                onChange={(list) => set("dependents", list)}
              />
            </div>
          </div>
        </Section>

        <div className="sticky bottom-0 bg-white/90 backdrop-blur border-t border-slate-200 -mx-6 lg:-mx-8 px-6 lg:px-8 py-4 flex items-center justify-end gap-2">
          <button
            type="submit"
            disabled={update.isPending}
            className="inline-flex items-center gap-2 bg-brand-600 hover:bg-brand-700 text-white font-semibold px-4 py-2 rounded-lg disabled:opacity-50"
          >
            {update.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            Save Changes
          </button>
        </div>
      </form>
    </div>
  );
}

// ── Primitives ───────────────────────────────────────────────────────────────

function Section({
  icon: Icon, title, badge, children,
}: { icon: any; title: string; badge?: string; children: React.ReactNode }) {
  return (
    <section className="bg-white rounded-xl border border-slate-200 p-6">
      <header className="flex items-center gap-2 mb-4">
        <Icon className="w-4 h-4 text-brand-600" />
        <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wide">{title}</h2>
        {badge && (
          <span className="ml-auto text-[10px] font-bold bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full">
            {badge}
          </span>
        )}
      </header>
      <div className="space-y-3">{children}</div>
    </section>
  );
}

function Row({ children }: { children: React.ReactNode }) {
  return <div className="grid md:grid-cols-3 gap-3">{children}</div>;
}

function Field({
  label, value, onChange, type = "text", placeholder, textarea, disabled, note,
}: {
  label: string;
  value: string | null | undefined;
  onChange?: (v: string | null) => void;
  type?: string;
  placeholder?: string;
  textarea?: boolean;
  disabled?: boolean;
  note?: string;
}) {
  const shared = "w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:ring-2 focus:ring-brand-500 focus:border-brand-500 disabled:bg-slate-50 disabled:text-slate-500";
  return (
    <label className="block">
      <span className="text-xs font-semibold text-slate-600 mb-1 block">{label}</span>
      {textarea ? (
        <textarea
          rows={2}
          className={shared}
          value={value ?? ""}
          disabled={disabled}
          placeholder={placeholder}
          onChange={(e) => onChange?.(e.target.value === "" ? null : e.target.value)}
        />
      ) : (
        <input
          type={type}
          className={shared}
          value={value ?? ""}
          disabled={disabled}
          placeholder={placeholder}
          onChange={(e) => onChange?.(e.target.value === "" ? null : e.target.value)}
        />
      )}
      {note && <span className="text-[10px] text-slate-400 mt-1 block">{note}</span>}
    </label>
  );
}

function Select({
  label, value, onChange, options,
}: { label: string; value: string | null | undefined; onChange: (v: string | null) => void; options: string[] }) {
  return (
    <label className="block">
      <span className="text-xs font-semibold text-slate-600 mb-1 block">{label}</span>
      <select
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value === "" ? null : e.target.value)}
        className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
      >
        <option value="">—</option>
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </label>
  );
}

function MembershipEditor({
  value, onChange,
}: { value: HRMembership[]; onChange: (v: HRMembership[]) => void }) {
  const add = () => onChange([...value, { body: "", membership_number: "", expires_at: null }]);
  const remove = (i: number) => onChange(value.filter((_, idx) => idx !== i));
  const update = (i: number, patch: Partial<HRMembership>) =>
    onChange(value.map((m, idx) => (idx === i ? { ...m, ...patch } : m)));

  return (
    <div className="space-y-3">
      {value.length === 0 && (
        <p className="text-sm text-slate-500 italic">No professional memberships yet.</p>
      )}
      {value.map((m, i) => (
        <div key={i} className="grid md:grid-cols-4 gap-3 items-end border border-slate-100 rounded-lg p-3">
          <Field label="Body" value={m.body ?? ""} onChange={(v) => update(i, { body: v ?? "" })} placeholder="ICAN / NBA / NMA" />
          <Field label="Membership #" value={m.membership_number ?? ""} onChange={(v) => update(i, { membership_number: v ?? "" })} />
          <Field label="Expires" type="date" value={m.expires_at ?? ""} onChange={(v) => update(i, { expires_at: v })} />
          <button type="button" onClick={() => remove(i)} className="text-xs text-red-600 font-semibold hover:underline">Remove</button>
        </div>
      ))}
      <button type="button" onClick={add} className="text-xs font-semibold text-brand-600 hover:underline">+ Add membership</button>
    </div>
  );
}

function DependentsEditor({
  value, onChange,
}: { value: HRDependent[]; onChange: (v: HRDependent[]) => void }) {
  const add = () => onChange([...value, { name: "", relationship: "", date_of_birth: null }]);
  const remove = (i: number) => onChange(value.filter((_, idx) => idx !== i));
  const update = (i: number, patch: Partial<HRDependent>) =>
    onChange(value.map((d, idx) => (idx === i ? { ...d, ...patch } : d)));

  return (
    <div className="space-y-3">
      {value.length === 0 && (
        <p className="text-sm text-slate-500 italic">No dependents added.</p>
      )}
      {value.map((d, i) => (
        <div key={i} className="grid grid-cols-1 gap-2 border border-slate-100 rounded-lg p-3">
          <Field label="Name" value={d.name ?? ""} onChange={(v) => update(i, { name: v ?? "" })} />
          <Field label="Relationship" value={d.relationship ?? ""} onChange={(v) => update(i, { relationship: v ?? "" })} placeholder="Son / Daughter / Parent" />
          <Field label="Date of Birth" type="date" value={d.date_of_birth ?? ""} onChange={(v) => update(i, { date_of_birth: v })} />
          <button type="button" onClick={() => remove(i)} className="text-xs text-red-600 font-semibold hover:underline self-end">Remove</button>
        </div>
      ))}
      <button type="button" onClick={add} className="text-xs font-semibold text-brand-600 hover:underline">+ Add dependent</button>
    </div>
  );
}

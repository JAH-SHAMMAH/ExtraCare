"use client";

import { useState } from "react";
import {
  useJobs, useCreateJob, useUpdateJob, useDeleteJob,
  useApplicants, useCreateApplicant, useUpdateApplicant, useDeleteApplicant,
} from "@/hooks/useHrExtended";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn } from "@/lib/utils";
import { Briefcase, Plus, X, Loader2, Trash2, AlertTriangle, ArrowLeft, Users2, Lock } from "lucide-react";

const STAGES = ["applied", "screening", "interview", "offer", "hired", "rejected"];
const STAGE_STYLE: Record<string, string> = {
  applied: "bg-slate-50 text-slate-600 border-slate-200",
  screening: "bg-blue-50 text-blue-700 border-blue-200",
  interview: "bg-violet-50 text-violet-700 border-violet-200",
  offer: "bg-amber-50 text-amber-700 border-amber-200",
  hired: "bg-emerald-50 text-emerald-700 border-emerald-200",
  rejected: "bg-rose-50 text-rose-700 border-rose-200",
};

export default function RecruitmentPage() {
  const canWrite = useHasPermission("hr:write");
  const [openJob, setOpenJob] = useState<any | null>(null);
  if (openJob) return <JobDetail job={openJob} canWrite={canWrite} onBack={() => setOpenJob(null)} />;
  return <JobsList canWrite={canWrite} onOpen={setOpenJob} />;
}

function JobsList({ canWrite, onOpen }: { canWrite: boolean; onOpen: (j: any) => void }) {
  const { data, isLoading, isError, refetch } = useJobs();
  const create = useCreateJob();
  const [show, setShow] = useState(false);
  const [f, setF] = useState({ title: "", department: "", employment_type: "full_time", positions: "1", description: "" });
  const reset = () => { setF({ title: "", department: "", employment_type: "full_time", positions: "1", description: "" }); setShow(false); };

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>HR Manager</span><span>/</span><span className="text-brand-600 font-semibold">Recruitment</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Recruitment</h1>
          <p className="text-slate-500 text-sm mt-0.5">Job openings and the applicant pipeline.</p>
        </div>
        {canWrite && <button onClick={() => { reset(); setShow(true); }} className="btn-primary gap-2"><Plus size={15} /> New Opening</button>}
      </div>

      {show && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div><label className="label">Title *</label><input value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} className="input" placeholder="Mathematics Teacher" /></div>
            <div><label className="label">Department</label><input value={f.department} onChange={(e) => setF({ ...f, department: e.target.value })} className="input" /></div>
            <div><label className="label">Type</label><select value={f.employment_type} onChange={(e) => setF({ ...f, employment_type: e.target.value })} className="input">{["full_time", "part_time", "contract"].map((t) => <option key={t} value={t}>{t.replace("_", " ")}</option>)}</select></div>
            <div><label className="label">Positions</label><input type="number" value={f.positions} onChange={(e) => setF({ ...f, positions: e.target.value })} className="input" /></div>
            <div className="md:col-span-2"><label className="label">Description</label><textarea value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} className="input min-h-[80px]" /></div>
          </div>
          <div className="flex justify-end gap-3"><button onClick={reset} className="btn-secondary">Cancel</button><button onClick={() => create.mutate({ title: f.title.trim(), department: f.department || null, employment_type: f.employment_type, positions: Number(f.positions) || 1, description: f.description || null }, { onSuccess: reset })} disabled={!f.title.trim() || create.isPending} className="btn-primary gap-2">{create.isPending && <Loader2 size={15} className="animate-spin" />}Create</button></div>
        </div>
      )}

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-28 bg-slate-100 rounded-xl animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load openings.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></div>
      ) : (data ?? []).length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400"><Briefcase size={36} className="mb-3 opacity-40" /><p className="font-semibold">No job openings yet</p></div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {data!.map((j) => (
            <button key={j.id} onClick={() => onOpen(j)} className="text-left bg-white rounded-xl border border-slate-200 p-5 hover:shadow-md transition-shadow">
              <div className="flex items-start justify-between mb-2">
                <h3 className="text-sm font-bold text-slate-900">{j.title}</h3>
                <span className={cn("badge capitalize", j.status === "open" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-100 text-slate-500 border-slate-200")}>{j.status}</span>
              </div>
              <p className="text-xs text-slate-500 mb-3">{[j.department, j.employment_type?.replace("_", " ")].filter(Boolean).join(" · ") || "—"}</p>
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-500">{j.positions} position{j.positions === 1 ? "" : "s"}</span>
                <span className="inline-flex items-center gap-1 font-semibold text-slate-700"><Users2 size={13} /> {j.applicant_count} applicant{j.applicant_count === 1 ? "" : "s"}</span>
              </div>
            </button>
          ))}
        </div>
      )}
      {!canWrite && <p className="text-xs text-slate-400 mt-4 flex items-center gap-1"><Lock size={12} /> Recruitment is HR-admin only (hr:write).</p>}
    </div>
  );
}

function JobDetail({ job, canWrite, onBack }: { job: any; canWrite: boolean; onBack: () => void }) {
  const { data: applicants, isLoading } = useApplicants(job.id);
  const create = useCreateApplicant();
  const update = useUpdateApplicant();
  const del = useDeleteApplicant();
  const updateJob = useUpdateJob();
  const delJob = useDeleteJob();
  const [adding, setAdding] = useState(false);
  const [a, setA] = useState({ name: "", email: "", phone: "" });

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <button onClick={onBack} className="flex items-center gap-2 text-xs text-slate-500 hover:text-slate-700 mb-4"><ArrowLeft size={14} /> Back to openings</button>
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-black text-slate-900">{job.title}</h1>
          <p className="text-sm text-slate-500 mt-1">{[job.department, job.employment_type?.replace("_", " ")].filter(Boolean).join(" · ")}</p>
        </div>
        {canWrite && (
          <div className="flex items-center gap-2">
            <button onClick={() => updateJob.mutate({ id: job.id, data: { status: job.status === "open" ? "closed" : "open" } }, { onSuccess: onBack })} className="btn-secondary">{job.status === "open" ? "Close" : "Reopen"}</button>
            <button onClick={() => { if (confirm("Delete this opening?")) { delJob.mutate(job.id); onBack(); } }} className="text-slate-400 hover:text-red-600 p-2"><Trash2 size={15} /></button>
          </div>
        )}
      </div>

      {canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-4 mb-4 flex flex-wrap gap-2 items-end">
          <div className="flex-1 min-w-[160px]"><label className="label">Name *</label><input value={a.name} onChange={(e) => setA({ ...a, name: e.target.value })} className="input" /></div>
          <div className="flex-1 min-w-[160px]"><label className="label">Email</label><input value={a.email} onChange={(e) => setA({ ...a, email: e.target.value })} className="input" /></div>
          <div className="min-w-[130px]"><label className="label">Phone</label><input value={a.phone} onChange={(e) => setA({ ...a, phone: e.target.value })} className="input" /></div>
          <button onClick={() => create.mutate({ job_id: job.id, name: a.name.trim(), email: a.email || null, phone: a.phone || null, stage: "applied" }, { onSuccess: () => setA({ name: "", email: "", phone: "" }) })} disabled={!a.name.trim() || create.isPending} className="btn-primary justify-center">{create.isPending ? <Loader2 size={14} className="animate-spin" /> : "Add"}</button>
        </div>
      )}

      {isLoading ? (
        <div className="space-y-2">{Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-14 bg-slate-100 rounded-lg animate-pulse" />)}</div>
      ) : (applicants ?? []).length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-12 text-slate-400"><Users2 size={30} className="mb-2 opacity-40" /><p className="font-semibold">No applicants yet</p></div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
          {applicants!.map((ap) => (
            <div key={ap.id} className="flex items-center gap-3 px-5 py-3.5">
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-slate-800 truncate">{ap.name}</p>
                <p className="text-xs text-slate-400 truncate">{[ap.email, ap.phone].filter(Boolean).join(" · ") || "—"}</p>
              </div>
              {canWrite ? (
                <select value={ap.stage} onChange={(e) => update.mutate({ id: ap.id, data: { stage: e.target.value } })} className={cn("text-xs font-semibold rounded-lg border px-2 py-1 capitalize", STAGE_STYLE[ap.stage])}>
                  {STAGES.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              ) : <span className={cn("badge capitalize", STAGE_STYLE[ap.stage])}>{ap.stage}</span>}
              {canWrite && <button onClick={() => del.mutate(ap.id)} className="text-slate-400 hover:text-red-600 p-1"><X size={15} /></button>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

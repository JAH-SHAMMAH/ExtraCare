"use client";

/**
 * Behaviour/skills ratings and Nursery achievements, entered for a whole class.
 *
 * Replaces the old grid on Report Entry, which had three faults:
 *  - its dropdown offered a hardcoded Excellent/Good/Fair/Poor, ignoring the
 *    school's own key (Fairview's is 1-5), so a saved value never matched the card;
 *  - it seeded every cell as null and sent them all on save, so touching ONE cell
 *    for a pupil cleared every other rating already saved for that pupil;
 *  - it had no way to write a comment, which is the whole of a Nursery report.
 *
 * Only cells the teacher changed are sent. Options come from each domain's own
 * rating scale (the class grid carries them), and a Nursery class gets a per-pupil
 * achievement + sample-picture form instead of a matrix.
 */

import { useMemo, useState } from "react";
import { Loader2, Save, ImagePlus, X } from "lucide-react";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";
import { useClassDomainRatings, useSaveDomainRatings } from "@/hooks/useSchool";
import { uploadApi, schoolApi } from "@/lib/api";

type Cell = { rating: string | null; comment: string | null; photo_url: string | null };
const key = (s: string, d: string) => `${s}:${d}`;

export function DomainRatingsEntry({ classId, termId, canWrite }: { classId: string; termId: string; canWrite: boolean }) {
  const { data: g, isLoading, isError } = useClassDomainRatings(classId, termId);
  const save = useSaveDomainRatings();
  const [edits, setEdits] = useState<Record<string, Partial<Cell>>>({});
  const [studentId, setStudentId] = useState("");
  const [uploading, setUploading] = useState("");

  const domains: any[] = (g as any)?.domains ?? [];
  const students: any[] = (g as any)?.students ?? [];
  const isNursery = domains.some((d) => String(d.domain_type).startsWith("eyfs"));

  const saved = (sid: string, did: string): Cell => {
    const c = students.find((s) => s.student_id === sid)?.ratings?.[did] ?? {};
    return { rating: c.rating ?? null, comment: c.comment ?? null, photo_url: c.photo_url ?? null };
  };
  const current = (sid: string, did: string): Cell => ({ ...saved(sid, did), ...(edits[key(sid, did)] ?? {}) });
  const edit = (sid: string, did: string, patch: Partial<Cell>) =>
    setEdits((p) => ({ ...p, [key(sid, did)]: { ...(p[key(sid, did)] ?? {}), ...patch } }));
  const dirty = Object.keys(edits).length;

  const submit = async () => {
    const bySid: Record<string, any[]> = {};
    for (const k of Object.keys(edits)) {
      const [sid, did] = k.split(":");
      const c = current(sid, did);
      // photo_url is named only when it changed, so saving words never drops a picture.
      const item: any = { domain_id: did, rating: c.rating, comment: c.comment };
      if ("photo_url" in edits[k]) item.photo_url = c.photo_url ?? "";
      (bySid[sid] ??= []).push(item);
    }
    try {
      for (const [sid, ratings] of Object.entries(bySid)) {
        await save.mutateAsync({ student_id: sid, data: { term_id: termId, ratings } });
      }
      setEdits({});
    } catch { /* the hook already toasts the server's reason; keep the edits */ }
  };

  const pickPhoto = async (sid: string, did: string, file: File | undefined) => {
    if (!file) return;
    setUploading(key(sid, did));
    try {
      const r = await uploadApi.reportPhoto(file);
      edit(sid, did, { photo_url: r.url });
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Could not upload the picture.");
    } finally {
      setUploading("");
    }
  };

  if (isLoading) return <div className="py-8 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></div>;
  // A failed load must not look like an unrated class: a teacher would re-enter
  // what is already saved.
  if (isError) return (
    <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
      <span className="font-semibold">Existing ratings could not be loaded.</span> Reload before entering, or you may overwrite what is saved.
    </div>
  );
  if (!domains.length) return (
    <div className="bg-white rounded-xl border border-dashed border-slate-200 p-8 text-center text-sm text-slate-500">
      No behaviour, skills or learning goals are set up for this class&apos;s section yet.
    </div>
  );

  const saveBtn = canWrite && (
    <button onClick={submit} disabled={!dirty || save.isPending} className="btn-primary gap-2">
      {save.isPending ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />}
      Save{dirty ? ` (${dirty} change${dirty > 1 ? "s" : ""})` : ""}
    </button>
  );

  if (isNursery) {
    const areas = domains.filter((d) => d.domain_type === "eyfs_area");
    const goalsOf = (a: any) => domains.filter((d) => d.parent_domain_id === a.domain_id);
    let n = 0;
    return (
      <div className="space-y-4">
        <AreaTopicsEditor classId={classId} termId={termId} areas={areas} saved={(g as any)?.topics ?? {}} canWrite={canWrite} />
        <div className="flex flex-wrap items-end gap-3 justify-between">
          <div>
            <label className="label">Pupil</label>
            <select value={studentId} onChange={(e) => setStudentId(e.target.value)} className="input min-w-[220px]">
              <option value="">— Select —</option>
              {students.map((s) => <option key={s.student_id} value={s.student_id}>{s.student_name}</option>)}
            </select>
          </div>
          {saveBtn}
        </div>
        {!studentId ? (
          <p className="text-sm text-slate-400 py-6 text-center">Choose a pupil to write their achievements.</p>
        ) : areas.map((a) => (
          <div key={a.domain_id} className="bg-white rounded-xl border border-slate-200 p-4">
            <h3 className="font-bold text-slate-900 mb-3">{a.name}</h3>
            <div className="space-y-4">
              {goalsOf(a).map((d) => {
                n += 1;
                const c = current(studentId, d.domain_id);
                const busy = uploading === key(studentId, d.domain_id);
                return (
                  <div key={d.domain_id} className="grid md:grid-cols-[1fr_160px] gap-3">
                    <div>
                      <label className="text-xs font-bold uppercase text-slate-600">ELG {n} · {d.name}</label>
                      <textarea
                        value={c.comment ?? ""} disabled={!canWrite} rows={3}
                        onChange={(e) => edit(studentId, d.domain_id, { comment: e.target.value })}
                        placeholder="What this child can do now…"
                        className="input w-full mt-1" />
                      {d.options?.length > 0 && (
                        <select value={c.rating ?? ""} disabled={!canWrite}
                          onChange={(e) => edit(studentId, d.domain_id, { rating: e.target.value || null })}
                          className="input mt-1 text-xs">
                          <option value="">— rating —</option>
                          {d.options.map((o: string) => <option key={o} value={o}>{o}</option>)}
                        </select>
                      )}
                    </div>
                    <div className="text-xs">
                      <p className="font-bold uppercase text-slate-600 mb-1">Sample picture</p>
                      {c.photo_url ? (
                        <div className="relative">
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img src={c.photo_url} alt="" className="w-full h-24 object-cover rounded border border-slate-200" />
                          {canWrite && <button type="button" aria-label="Remove picture" onClick={() => edit(studentId, d.domain_id, { photo_url: null })}
                            className="absolute top-1 right-1 bg-white/90 rounded-full p-0.5"><X size={12} /></button>}
                        </div>
                      ) : canWrite ? (
                        <label className="flex flex-col items-center justify-center h-24 border border-dashed border-slate-300 rounded cursor-pointer text-slate-400 hover:bg-slate-50">
                          {busy ? <Loader2 size={16} className="animate-spin" /> : <ImagePlus size={18} />}
                          <span className="mt-1">{busy ? "Uploading…" : "Add picture"}</span>
                          <input type="file" accept="image/*" className="hidden"
                            onChange={(e) => pickPhoto(studentId, d.domain_id, e.target.files?.[0])} />
                        </label>
                      ) : <p className="text-slate-300">None</p>}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    );
  }

  // Matrix: pupils down, skills across, one dropdown per cell from the domain's own scale.
  const types = Array.from(new Set(domains.map((d) => d.domain_type)));
  return (
    <div className="space-y-4">
      <div className="flex justify-end">{saveBtn}</div>
      {types.map((t) => {
        const cols = domains.filter((d) => d.domain_type === t);
        return (
          <div key={t} className="bg-white rounded-xl border border-slate-200 p-4 overflow-x-auto">
            <h3 className="font-semibold text-slate-900 mb-3 capitalize">{t}</h3>
            <table className="w-full text-xs">
              <thead><tr className="border-b border-slate-200 bg-slate-50">
                <th className="text-left px-3 py-2">Pupil</th>
                {cols.map((d) => <th key={d.domain_id} className="px-2 py-2 text-center font-semibold">{d.name}</th>)}
              </tr></thead>
              <tbody>
                {students.map((s) => (
                  <tr key={s.student_id} className="border-b border-slate-100">
                    <td className="px-3 py-2 whitespace-nowrap">{s.student_name}</td>
                    {cols.map((d) => (
                      <td key={d.domain_id} className="px-1 py-1 text-center">
                        <select
                          value={current(s.student_id, d.domain_id).rating ?? ""} disabled={!canWrite}
                          onChange={(e) => edit(s.student_id, d.domain_id, { rating: e.target.value || null })}
                          className={`w-full px-1 py-1 border rounded bg-white ${edits[key(s.student_id, d.domain_id)] ? "border-brand-500" : "border-slate-300"}`}>
                          <option value="">—</option>
                          {(d.options ?? []).map((o: string) => <option key={o} value={o}>{o}</option>)}
                        </select>
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      })}
    </div>
  );
}

/** "The topics we have covered so far" for the whole class, one box per area of
 *  learning. Printed once at the top of every pupil's Nursery report. */
export function AreaTopicsEditor({ classId, termId, areas, saved, canWrite }: {
  classId: string; termId: string; areas: any[]; saved: Record<string, string>; canWrite: boolean;
}) {
  const qc = useQueryClient();
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const value = (id: string) => draft[id] ?? saved[id] ?? "";
  const changed = Object.keys(draft).filter((id) => draft[id] !== (saved[id] ?? ""));
  const save = async () => {
    setBusy(true);
    try {
      await schoolApi.grades.saveAreaTopics(classId, { term_id: termId, topics: Object.fromEntries(changed.map((id) => [id, draft[id]])) });
      await qc.invalidateQueries({ queryKey: ["class-domain-ratings"] });
      setDraft({});
      toast.success("Topics saved.");
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Could not save the topics.");
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4">
      <h3 className="font-bold text-slate-900">Topics covered this term</h3>
      <p className="text-xs text-slate-500 mb-3">For the whole class. Printed at the top of every pupil&apos;s report.</p>
      <div className="space-y-3">
        {areas.map((a) => (
          <div key={a.domain_id}>
            <label className="text-xs font-bold uppercase text-slate-600">{a.name}</label>
            <textarea rows={2} disabled={!canWrite} value={value(a.domain_id)}
              onChange={(e) => setDraft((p) => ({ ...p, [a.domain_id]: e.target.value }))}
              placeholder="e.g. Listening to stories, following directions…" className="input w-full mt-1" />
          </div>
        ))}
      </div>
      {canWrite && (
        <button onClick={save} disabled={!changed.length || busy} className="btn-primary gap-2 mt-3">
          {busy ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />} Save topics
        </button>
      )}
    </div>
  );
}

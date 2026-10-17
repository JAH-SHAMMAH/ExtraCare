"use client";

import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { useClasses } from "@/hooks/useSchool";
import { useTerms, useSubTerms, useBroadsheet, useReportCard, useReportCardsBulk, useCommentGrid, useSaveComments } from "@/hooks/usePlatform";
import { Loader2, Printer, FileText, Save, Settings2 } from "lucide-react";

/** Sentinel for the "every pupil in the class" option in the student picker. */
const ALL = "__ALL__";

export function BulkPrintTab() {
  const classesData: any = useClasses({ page_size: 200 }).data;
  const classes: any[] = classesData?.items ?? classesData ?? [];
  const { data: terms = [] } = useTerms();
  const { data: subs = [] } = useSubTerms();
  const [classId, setClassId] = useState("");
  const [termId, setTermId] = useState("");
  const [subTermId, setSubTermId] = useState("");
  const [studentId, setStudentId] = useState("");
  const { data: bs } = useBroadsheet({ class_id: classId, term_id: termId, sub_term_id: subTermId });
  // studentId === ALL renders every card in the class, one per printed page.
  const isAll = studentId === ALL;
  const { data: card, isLoading } = useReportCard({ student_id: isAll ? "" : studentId, term_id: termId, sub_term_id: subTermId });
  const { data: allCards, isLoading: allLoading } = useReportCardsBulk(
    { class_id: classId, term_id: termId, sub_term_id: subTermId }, isAll);

  const students: any[] = bs?.rows ?? [];
  const num = (v: any) => (v == null ? "–" : Number(v));
  const cards: any[] = isAll ? (allCards ?? []) : card ? [card] : [];
  const busy = isAll ? allLoading : isLoading;
  // The flag is a property of the (term, sub-term) setup, not of the pupil, so
  // every card in a bulk run carries the same value -- the first is enough. The
  // broadsheet's copy is the fallback for "All students", where no single card
  // has been fetched yet.
  const notConfigured: boolean = cards[0]?.not_configured ?? (bs as any)?.not_configured ?? false;

  return (
    <div className="space-y-4">
      <style>{`@media print {
        body * { visibility: hidden !important; }
        #report-card, #report-card * { visibility: visible !important; }
        #report-card { position: absolute; left: 0; top: 0; width: 100%; }
        /* One card per sheet in bulk mode; the last must not emit a trailing blank page. */
        .card-page { break-after: page; page-break-after: always; }
        .card-page:last-child { break-after: auto; page-break-after: auto; }
      }`}</style>

      <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-wrap items-end gap-3 no-print">
        <div><label className="label">Class</label><select value={classId} onChange={(e) => { setClassId(e.target.value); setStudentId(""); }} className="input"><option value="">— Select —</option>{classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></div>
        <div><label className="label">Term</label><select value={termId} onChange={(e) => setTermId(e.target.value)} className="input"><option value="">— Select —</option>{(terms as any[]).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select></div>
        <div><label className="label">Sub-term</label><select value={subTermId} onChange={(e) => setSubTermId(e.target.value)} className="input"><option value="">— Select —</option>{(subs as any[]).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></div>
        <div><label className="label">Student</label><select value={studentId} onChange={(e) => setStudentId(e.target.value)} disabled={!bs} className="input min-w-[180px]"><option value="">— Select —</option><option value={ALL}>All students ({students.length}) — bulk print</option>{students.map((r) => <option key={r.student_id} value={r.student_id}>{r.student_name}</option>)}</select></div>
        {cards.length > 0 && <button onClick={() => window.print()} className="btn-primary gap-2 ml-auto"><Printer size={15} /> Print{isAll ? ` ${cards.length} cards` : ""}</button>}
      </div>

      {!studentId ? (
        <div className="bg-white rounded-xl border border-dashed border-slate-200 py-16 text-center text-slate-400 no-print"><FileText size={30} className="mx-auto mb-3 opacity-40" /><p className="text-sm">Choose a class, term, sub-term and student — or &ldquo;All students&rdquo; to bulk-print the whole class.</p></div>
      ) : busy ? (
        <div className="py-16 text-center no-print"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /><p className="text-xs text-slate-400 mt-2">{isAll ? "Building every card in the class…" : "Loading…"}</p></div>
      ) : notConfigured ? (
        /* No column exists for this term + sub-term, so a card here would be a
           blank table. Checked BEFORE "no report cards for this selection",
           which reads as "nothing published yet" and sends the user to chase
           marks that have nowhere to land. Until `_pick_display_cumulative`
           stopped borrowing, this case printed ANOTHER sub-term's figures under
           this sub-term's heading. */
        <div className="bg-white rounded-xl border border-amber-200 py-16 px-6 text-center no-print">
          <Settings2 size={30} className="mx-auto mb-3 text-amber-500" />
          <p className="text-sm font-bold text-slate-800 mb-1">
            This sub-term isn&rsquo;t set up yet
          </p>
          <p className="text-sm text-amber-800 max-w-md mx-auto leading-relaxed">
            No report column is configured for this term and sub-term, so there
            is nothing to print.
          </p>
          <p className="text-xs text-slate-500 mt-3 max-w-md mx-auto leading-relaxed">
            Add its assessments and cumulative columns under{" "}
            <span className="font-semibold">Report Setup &rarr; Result View</span>.
          </p>
        </div>
      ) : cards.length === 0 ? (
        <div className="bg-white rounded-xl border border-dashed border-slate-200 py-16 text-center text-slate-400 no-print"><p className="text-sm">No report cards for this selection.</p></div>
      ) : (
        <div id="report-card" className="space-y-6">
          {cards.map((c: any) => (
            <div key={c.student_id} className="card-page bg-white rounded-xl border border-slate-300 p-6 max-w-4xl mx-auto text-slate-900 [print-color-adjust:exact] [-webkit-print-color-adjust:exact]">
              <Card card={c} num={num} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/** One pupil's full report in a pop-up, opened from the Reports View list.
 *  `print` opens it and immediately offers the browser's Save-as-PDF dialog. */
export function StudentReportDialog({ studentId, termId, subTermId, print, onClose }: {
  studentId: string; termId: string; subTermId: string; print?: boolean; onClose: () => void;
}) {
  const { data: card, isLoading } = useReportCard({ student_id: studentId, term_id: termId, sub_term_id: subTermId });
  const num = (v: any) => (v == null ? "–" : Number(v));
  const ready = !!card && !card.not_configured;
  useEffect(() => {
    if (print && ready) { const t = setTimeout(() => window.print(), 300); return () => clearTimeout(t); }
  }, [print, ready]);
  return (
    <div className="fixed inset-0 z-50 bg-black/50 overflow-y-auto p-4 no-print-bg" role="dialog" aria-label="Student report">
      <style>{`@media print {
        body * { visibility: hidden !important; }
        #single-report, #single-report * { visibility: visible !important; }
        #single-report { position: absolute; left: 0; top: 0; width: 100%; }
      }`}</style>
      <div className="max-w-4xl mx-auto">
        <div className="flex justify-end gap-2 mb-2 no-print print:hidden">
          {ready && <button onClick={() => window.print()} className="btn-primary gap-2"><Printer size={15} /> Export PDF</button>}
          <button onClick={onClose} className="btn-secondary">Close</button>
        </div>
        {isLoading ? (
          <div className="bg-white rounded-xl py-16 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></div>
        ) : !card || card.not_configured ? (
          <div className="bg-white rounded-xl py-16 px-6 text-center text-sm text-slate-500">No report is available for this pupil in the chosen term yet.</div>
        ) : (
          <div id="single-report" className="bg-white rounded-xl border border-slate-300 p-6 text-slate-900 [print-color-adjust:exact] [-webkit-print-color-adjust:exact]">
            <Card card={card} num={num} />
          </div>
        )}
      </div>
    </div>
  );
}

export function Card({ card, num }: { card: any; num: (v: any) => any }) {
  const b = card.branding || {};
  // Both operands checked, not just the denominator. `null / 60` is 0 in JS, so
  // a missing `present` beside a real `total` would have printed "0%" — an
  // unmarked figure rendering as a real one, which is the mistake this file
  // avoids everywhere else. The service never returns one without the other,
  // but a card should not depend on that to avoid asserting a child was absent
  // all term.
  const attPct = (card.attendance_total && card.attendance_present != null)
    ? Math.round((card.attendance_present / card.attendance_total) * 100)
    : null;
  // The Sessional Score appears only once more than one term has marks. A mean
  // of a single term is that term's own average, and printing it under a
  // different name would be the same number claiming to be a session's work.
  const sessionalTerms = card.sessional_terms ?? [];
  const showSessional = card.sessional_score != null && (card.sessional_terms_counted ?? 0) > 1;
  const partialSession = showSessional && card.sessional_terms_counted < sessionalTerms.length;
  // The Teacher's Remark column appears only when at least one subject carries
  // one, so a card from a school that does not use them keeps its old width.
  const showSubjectComments = (card.subjects ?? []).some((r: any) => (r.comment ?? "").trim());
  // Date on the signature line: when the card was produced.
  const printedOn = new Date().toLocaleDateString("en-GB");
  // Template dispatch. Nursery prints no marks at all (areas of learning rated
  // A/E/SNS); Junior and Secondary print the marks table plus behaviour and skills.
  // An unclassified section (report_key null) keeps the marks layout, the old default.
  const isNursery = card.report_key === "nursery-report";
  const isJunior = card.report_key === "junior-report";
  const blocks: any[] = card.domain_blocks ?? [];
  const sideBlocks = blocks.filter((x) => x.domain_type === "affective" || x.domain_type === "psychomotor");
  const areaBlocks = blocks.filter((x) => x.domain_type === "eyfs_area");
  return (
    <>
      <div className="flex items-center gap-4 border-b-2 border-[#2f5f1f] pb-3">
        {/* Saved letterhead logo, else the school crest the portal itself ships. */}
        <img src={b.logo_url || "/logo-square.png"} alt="School logo" className="w-20 h-20 object-contain shrink-0" />
        <div className="flex-1 text-center">
          <h2 className="text-xl font-black tracking-tight">{b.school_name_alias || "SCHOOL REPORT"}</h2>
          {b.school_address && <p className="text-[11px] text-slate-600">{b.school_address}</p>}
          {b.school_email && <p className="text-[11px] text-slate-600">Email: {b.school_email}</p>}
          <p className="text-xs font-bold mt-1">{card.report_title} {b.school_name_alias ? "" : ""}</p>
        </div>
        {card.photo_url
          ? <img src={card.photo_url} alt={`${card.student_name} photo`} className="w-20 h-24 object-cover border border-slate-400 shrink-0" />
          : <div data-testid="photo-placeholder" className="w-20 h-24 border border-slate-400 bg-slate-50 shrink-0 flex items-end justify-center overflow-hidden" aria-label="No photo">
              <svg viewBox="0 0 24 24" className="w-16 h-16 text-slate-300" fill="currentColor"><circle cx="12" cy="8" r="4.5" /><path d="M3 24c0-5.5 4-9 9-9s9 3.5 9 9z" /></svg>
            </div>}
      </div>

      <table className="w-full text-xs mt-3 border border-slate-300">
        <tbody>
          <tr>
            <td className="border border-slate-300 px-2 py-1 font-bold bg-[#a0de8c]">Name</td>
            <td className="border border-slate-300 px-2 py-1">{card.student_name}</td>
            <td className="border border-slate-300 px-2 py-1 font-bold bg-[#a0de8c]">Class</td>
            <td className="border border-slate-300 px-2 py-1">{card.class_name || "—"}</td>
            <td className="border border-slate-300 px-2 py-1 font-bold bg-[#a0de8c]">{isNursery ? "Term" : "Position"}</td>
            <td className="border border-slate-300 px-2 py-1">{isNursery ? (card.term_name || "—") : `${card.position} of ${card.class_size}`}</td>
          </tr>
          {isNursery ? (
            <tr>
              <td className="border border-slate-300 px-2 py-1 font-bold bg-[#a0de8c]">Admission No</td>
              <td className="border border-slate-300 px-2 py-1">{card.admission_no || "—"}</td>
              <td className="border border-slate-300 px-2 py-1 font-bold bg-[#a0de8c]">Session</td>
              <td colSpan={3} className="border border-slate-300 px-2 py-1">{card.term_name || "—"}{card.sub_term_name ? ` · ${card.sub_term_name}` : ""}</td>
            </tr>
          ) : (<>
          <tr>
            <td className="border border-slate-300 px-2 py-1 font-bold bg-[#a0de8c]">Admission No</td>
            <td className="border border-slate-300 px-2 py-1">{card.admission_no || "—"}</td>
            <td className="border border-slate-300 px-2 py-1 font-bold bg-[#a0de8c]">Times School Opened</td>
            <td className="border border-slate-300 px-2 py-1">{card.attendance_total ?? "—"}</td>
            <td className="border border-slate-300 px-2 py-1 font-bold bg-[#a0de8c]">{isJunior ? "Times Absent" : "Times Punctual"}</td>
            <td className="border border-slate-300 px-2 py-1">{isJunior ? (card.attendance_absent ?? "—") : (card.attendance_punctual ?? "—")}</td>
          </tr>
          <tr>
            <td className="border border-slate-300 px-2 py-1 font-bold bg-[#a0de8c]">Times Present</td>
            <td className="border border-slate-300 px-2 py-1">{card.attendance_present ?? "—"}</td>
            <td className="border border-slate-300 px-2 py-1 font-bold bg-[#a0de8c]">% Attendance</td>
            <td className="border border-slate-300 px-2 py-1">{attPct != null ? `${attPct}%` : "—"}</td>
            <td className="border border-slate-300 px-2 py-1 font-bold bg-[#a0de8c]">Term</td>
            <td className="border border-slate-300 px-2 py-1">{card.term_name || "—"}{card.sub_term_name ? ` · ${card.sub_term_name}` : ""}</td>
          </tr>
          </>)}
        </tbody>
      </table>

      {!isNursery && (<>
      <table className="w-full text-xs mt-3 border border-slate-300">
        <thead>
          <tr className="bg-[#2f5f1f] text-white">
            <th className="border border-slate-300 px-2 py-1 text-left">Subject</th>
            {card.columns.map((c: any) => <th key={c.key} className="border border-slate-300 px-2 py-1 text-center">{c.name}{c.max_score != null ? <span className="block font-normal text-[9px] text-green-100">/{num(c.max_score)}</span> : null}</th>)}
            <th className="border border-slate-300 px-2 py-1 text-center">Grade</th>
            <th className="border border-slate-300 px-2 py-1 text-center">Remark</th>
            <th className="border border-slate-300 px-2 py-1 text-center">Arm Avg</th>
            {showSessional && <th className="border border-slate-300 px-2 py-1 text-center">Session Avg</th>}
            {showSubjectComments && <th className="border border-slate-300 px-2 py-1 text-left">Teacher&apos;s Remark</th>}
          </tr>
        </thead>
        <tbody>
          {card.subjects.map((r: any) => (
            <tr key={r.subject_id}>
              <td className="border border-slate-300 px-2 py-1 font-semibold">{r.subject_name}</td>
              {/* A column the server could not complete comes back null with its
                  name in incomplete_components. It says "not entered" rather than
                  showing a dash beside real figures, because a dash in a row of
                  numbers reads as a zero to a parent — and the underlying total
                  would have BEEN a deflated number, which is the thing being
                  prevented. */}
              {card.columns.map((c: any) => {
                const missing = (r.incomplete_components || []).includes(c.name);
                return (
                  <td key={c.key} className={cn(
                    "border border-slate-300 px-2 py-1 text-center",
                    missing ? "text-[9px] leading-tight text-amber-700" : "tabular-nums")}>
                    {missing ? "not entered" : num(r.values[c.key])}
                  </td>
                );
              })}
              <td className="border border-slate-300 px-2 py-1 text-center font-bold">{r.grade || "–"}</td>
              <td className="border border-slate-300 px-2 py-1 text-center">{r.remark || "–"}</td>
              <td className="border border-slate-300 px-2 py-1 text-center tabular-nums">{num(r.subject_arm_average)}</td>
              {showSessional && <td className="border border-slate-300 px-2 py-1 text-center tabular-nums">{r.sessional != null ? num(r.sessional) : "–"}</td>}
              {showSubjectComments && <td className="border border-slate-300 px-2 py-1 text-[10px] leading-snug">{r.comment || "–"}</td>}
            </tr>
          ))}
          {card.subjects.length === 0 && <tr><td colSpan={card.columns.length + 4 + (showSessional ? 1 : 0) + (showSubjectComments ? 1 : 0)} className="border border-slate-300 px-2 py-3 text-center text-slate-400">No marks entered for this pupil.</td></tr>}
        </tbody>
      </table>

      {/* Summary boxes beside the grading scale, matching the reference card. */}
      <div className="grid grid-cols-2 gap-3 mt-3 text-xs items-start">
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="border border-slate-300 p-2 text-center"><p className="font-bold text-slate-500">Student&apos;s Average</p><p className="text-lg font-black">{num(card.average)}</p></div>
            <div className="border border-slate-300 p-2 text-center"><p className="font-bold text-slate-500">Student&apos;s Total Score</p><p className="text-lg font-black">{num(card.total)}</p></div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="border border-slate-300 p-2 text-center"><p className="font-bold text-slate-500">Total Class Average</p><p className="text-lg font-black">{card.class_average != null ? num(card.class_average) : "–"}</p></div>
            <div className="border border-slate-300 p-2 text-center"><p className="font-bold text-slate-500">Overall Grade</p><p className="text-lg font-black">{card.grade || "–"}</p></div>
          </div>
          {showSessional && (
            <div className="border border-slate-300 p-2 text-center">
              <p className="font-bold text-slate-500">Sessional Score</p>
              <p className="text-lg font-black">{num(card.sessional_score)}</p>
              <p className="text-[9px] text-slate-500">
                {sessionalTerms.filter((t: any) => t.average != null).map((t: any) => `${t.term_name} ${num(t.average)}`).join("  ·  ")}
              </p>
              {/* Say so on the face of the card when the session is incomplete,
                  rather than letting a two-term mean read as a full year. */}
              {partialSession && (
                <p className="text-[9px] font-semibold text-slate-600">
                  Based on {card.sessional_terms_counted} of {sessionalTerms.length} terms
                </p>
              )}
            </div>
          )}
        </div>
        {card.bands.length > 0 ? (
          <table className="w-full text-[10px] border border-slate-300">
            <thead><tr className="bg-[#2f5f1f] text-white"><th colSpan={3} className="border border-slate-300 px-2 py-1">GRADING SCALE</th></tr></thead>
            <tbody>
              {card.bands.map((bnd: any) => (
                <tr key={bnd.grade}>
                  <td className="border border-slate-300 px-2 py-0.5 text-center tabular-nums">{bnd.min_score != null ? `${num(bnd.min_score)}-${num(bnd.max_score)}` : "–"}</td>
                  <td className="border border-slate-300 px-2 py-0.5 text-center font-bold">{bnd.grade}</td>
                  <td className="border border-slate-300 px-2 py-0.5">{bnd.remark || ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : <div />}
      </div>


      <RatingBlocks blocks={sideBlocks} clubs={card.report_key === "secondary-report" ? (card.clubs ?? []) : null} />
      </>)}
      {isNursery && <NurseryAreas blocks={areaBlocks} />}

      {/* Three fixed comments plus any configured custom slots. class_teacher and
          head come from StudentReport; pc is the newer per-(term, sub-term) store;
          slot_comments are the school's own named slots.

          The server omits a slot with no text rather than sending it empty, so a
          labelled blank row never reaches the card — a parent reads meaning into a
          blank box beside a heading, and "no comment written" is not a comment. */}
      {(card.class_teacher_comment || card.pc_comment || card.head_comment
        || (card.slot_comments?.length ?? 0) > 0) && (
        <table className="w-full text-xs mt-3 border border-slate-300">
          <thead><tr className="bg-[#2f5f1f] text-white"><th colSpan={2} className="border border-slate-300 px-2 py-1">COMMENTS</th></tr></thead>
          <tbody>
            {card.class_teacher_comment && <tr><td className="border border-slate-300 px-2 py-1 font-bold bg-[#a0de8c] w-40 align-top">{isJunior ? "Class Teacher's Remarks" : (b.class_teacher_title || "Class Teacher")}</td><td className="border border-slate-300 px-2 py-1">{card.class_teacher_comment}</td></tr>}
            {card.pc_comment && <tr><td className="border border-slate-300 px-2 py-1 font-bold bg-[#a0de8c] align-top">PC Teacher&apos;s Comment</td><td className="border border-slate-300 px-2 py-1">{card.pc_comment}</td></tr>}
            {card.head_comment && <tr><td className="border border-slate-300 px-2 py-1 font-bold bg-[#a0de8c] align-top">{isJunior ? "Head Teacher's Remarks" : `${b.school_head_title || "Head"}'s Comment`}</td><td className="border border-slate-300 px-2 py-1">{card.head_comment}</td></tr>}
            {(card.slot_comments ?? []).map((sc: any) => (
              <tr key={sc.comment_type_id}>
                <td className="border border-slate-300 px-2 py-1 font-bold bg-[#a0de8c] align-top">{sc.name}</td>
                <td className="border border-slate-300 px-2 py-1">{sc.text}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* Signature + date block, per the reference card. */}
      <table className="w-full text-xs mt-3 border border-slate-300">
        <tbody>
          <tr>
            <td className="border border-slate-300 px-2 py-1 font-bold bg-[#a0de8c] w-24">Signed:</td>
            <td className="border border-slate-300 px-2 py-6">
              {/* Branding stores ONE signature (head_signature_url); there is no
                  separate class-teacher signature field, so that is what prints. */}
              {b.head_signature_url ? <img src={b.head_signature_url} alt="" className="h-10 object-contain" /> : null}
            </td>
            <td className="border border-slate-300 px-2 py-1 font-bold bg-[#a0de8c] w-20">Date:</td>
            <td className="border border-slate-300 px-2 py-1 tabular-nums w-32">{printedOn}</td>
          </tr>
        </tbody>
      </table>
    </>
  );
}

/** Affective + Psychomotor, side by side, each line with its rating and one key
 *  underneath. A line nobody has rated prints blank rather than a default. */
function RatingBlocks({ blocks, clubs }: { blocks: any[]; clubs: string[] | null }) {
  if (!blocks.length) return null;
  return (
    <div className="grid grid-cols-2 gap-3 mt-3 text-xs items-start break-inside-avoid">
      {blocks.map((blk: any) => (
        <div key={blk.domain_type}>
          <table className="w-full border border-slate-300">
            <thead><tr className="bg-[#2f5f1f] text-white"><th colSpan={2} className="border border-slate-300 px-2 py-1 text-left">{blk.title}</th></tr></thead>
            <tbody>
              {blk.items.map((it: any) => (
                <tr key={it.domain_id}>
                  <td className="border border-slate-300 px-2 py-0.5">{it.name}</td>
                  <td className="border border-slate-300 px-2 py-0.5 text-center font-bold w-14">{it.rating || ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {blk.key?.length > 0 && (
            <p className="text-[10px] text-slate-600 mt-1">
              Key: {blk.key.map((k: any) => `${k.label}${k.meaning ? ` = ${k.meaning}` : ""}`).join("; ")}
            </p>
          )}
        </div>
      ))}
      {/* Secondary only: the reference prints a "Club/Sports Choice" box beside the key. */}
      {clubs && (
        <div>
          <table className="w-full border border-slate-300">
            <thead><tr className="bg-[#2f5f1f] text-white"><th className="border border-slate-300 px-2 py-1 text-left">Club/Sports Choice</th></tr></thead>
            <tbody>
              {clubs.length > 0
                ? clubs.map((c) => <tr key={c}><td className="border border-slate-300 px-2 py-0.5">{c}</td></tr>)
                : <tr><td className="border border-slate-300 px-2 py-3">&nbsp;</td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

/** Nursery: no marks. Fairview's page is one row per Early Learning Goal:
 *  Learning Area | ELG n | goal | ACHIEVEMENT (the teacher's sentence). The ELG
 *  number runs on across areas, as on the the reference page. A rating column appears
 *  only if the school uses a key or a goal has been rated. */
function NurseryAreas({ blocks }: { blocks: any[] }) {
  if (!blocks.length) {
    return <p className="mt-4 text-center text-xs text-slate-400 border border-dashed border-slate-200 py-6">No areas of learning have been set up for this class yet.</p>;
  }
  // Fairview's Nursery page always has the SAMPLE PICTURE column, filled or not.
  const showPhoto = true;
  const showRating = blocks.some((blk: any) => blk.key?.length > 0 || blk.items.some((it: any) => it.rating));
  let n = 0;
  return (
    <table className="w-full mt-3 text-xs border border-slate-300">
      <thead><tr className="bg-[#2f5f1f] text-white">
        <th className="border border-slate-300 px-2 py-1 text-left w-36">Learning Areas</th>
        <th className="border border-slate-300 px-2 py-1 text-left w-16">ELG</th>
        <th className="border border-slate-300 px-2 py-1 text-left w-44">&nbsp;</th>
        <th className="border border-slate-300 px-2 py-1 text-left">ACHIEVEMENT</th>
        {showRating && <th className="border border-slate-300 px-2 py-1 w-14">Rating</th>}
        {showPhoto && <th className="border border-slate-300 px-2 py-1 w-28">SAMPLE PICTURE</th>}
      </tr></thead>
      <tbody>
        {blocks.flatMap((blk: any, bi: number) => blk.items.map((it: any, ii: number) => {
          n += 1;
          return (
            <tr key={it.domain_id} className="align-top">
              {ii === 0 && <td rowSpan={blk.items.length} className="border border-slate-300 px-2 py-1 font-bold">{blk.title}</td>}
              <td className="border border-slate-300 px-2 py-1 font-bold underline">ELG {n}</td>
              <td className="border border-slate-300 px-2 py-1 font-bold uppercase">{it.name}</td>
              <td className="border border-slate-300 px-2 py-1 leading-snug">{it.comment || ""}</td>
              {showRating && <td className="border border-slate-300 px-2 py-1 text-center font-bold">{it.rating || ""}</td>}
              {showPhoto && <td className="border border-slate-300 p-1 text-center">{it.photo_url ? <img src={it.photo_url} alt="" className="w-24 h-20 object-cover mx-auto" /> : null}</td>}
            </tr>
          );
        }))}
      </tbody>
    </table>
  );
}

// ── S-4d: Head / PC comment grids ────────────────────────────────────────────

export function CommentGridTab({ kind, label }: { kind: "head" | "pc"; label: string }) {
  const classesData: any = useClasses({ page_size: 200 }).data;
  const classes: any[] = classesData?.items ?? classesData ?? [];
  const { data: terms = [] } = useTerms();
  const { data: subs = [] } = useSubTerms();
  const [classId, setClassId] = useState("");
  const [termId, setTermId] = useState("");
  const [subTermId, setSubTermId] = useState("");
  const { data: grid, isLoading, isError, error } = useCommentGrid({ class_id: classId, term_id: termId, sub_term_id: subTermId, kind });
  // The class picker offers every class, but the API only lets you write comments
  // for your own: head comments are admin-only and PC comments are limited to
  // that class's PC teacher. A refusal used to fall through to "No pupils in this
  // class", blaming the data for what is actually a permission answer.
  const denied = isError && (error as any)?.response?.status === 403;
  const save = useSaveComments();
  const [draft, setDraft] = useState<Record<string, string>>({});
  useEffect(() => {
    const seed: Record<string, string> = {};
    (grid?.rows ?? []).forEach((r: any) => { seed[r.student_id] = r.text || ""; });
    setDraft(seed);
  }, [grid]);

  const submit = () => save.mutate({
    term_id: termId, sub_term_id: subTermId, kind,
    items: (grid?.rows ?? []).map((r: any) => ({ student_id: r.student_id, text: draft[r.student_id] ?? "" })),
  });

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-wrap items-end gap-3">
        <div><label className="label">Class</label><select value={classId} onChange={(e) => setClassId(e.target.value)} className="input"><option value="">— Select —</option>{classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></div>
        <div><label className="label">Term</label><select value={termId} onChange={(e) => setTermId(e.target.value)} className="input"><option value="">— Select —</option>{(terms as any[]).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select></div>
        <div><label className="label">Sub-term</label><select value={subTermId} onChange={(e) => setSubTermId(e.target.value)} className="input"><option value="">— Select —</option>{(subs as any[]).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></div>
        {grid && (grid.rows?.length ?? 0) > 0 && <button onClick={submit} disabled={save.isPending} className="btn-primary gap-2 ml-auto">{save.isPending ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />} Save {label}</button>}
      </div>

      {!classId || !termId || !subTermId ? (
        <div className="bg-white rounded-xl border border-dashed border-slate-200 py-14 text-center text-slate-400"><p className="text-sm">Choose a class, term and sub-term to enter {label.toLowerCase()}s.</p></div>
      ) : isLoading ? (
        <div className="py-14 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></div>
      ) : denied ? (
        <div className="bg-white rounded-xl border border-amber-200 py-12 px-6 text-center">
          <p className="text-sm font-bold text-slate-800 mb-1">Not your class</p>
          <p className="text-sm text-amber-800 max-w-md mx-auto leading-relaxed">
            {(error as any)?.response?.data?.detail || `You cannot enter ${label.toLowerCase()}s for this class.`}
          </p>
        </div>
      ) : isError ? (
        <p className="text-sm text-slate-500 py-10 text-center bg-white rounded-xl border border-slate-200">
          Couldn&apos;t load this class. Try again.
        </p>
      ) : (grid?.rows ?? []).length === 0 ? (
        <p className="text-sm text-slate-400 py-10 text-center bg-white rounded-xl border border-slate-200">No pupils in this class.</p>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
          {(grid.rows as any[]).map((r) => (
            <div key={r.student_id} className="flex flex-col sm:flex-row sm:items-start gap-3 px-5 py-3">
              <span className="text-sm font-semibold text-slate-800 sm:w-48 shrink-0 pt-2">{r.student_name}</span>
              <textarea value={draft[r.student_id] ?? ""} onChange={(e) => setDraft((p) => ({ ...p, [r.student_id]: e.target.value }))} className="input flex-1" rows={2} placeholder={`${label}…`} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

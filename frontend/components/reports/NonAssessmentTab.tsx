"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";
import { useCommentTypes } from "@/hooks/usePlatform";
import { CommentGridTab } from "@/components/reports/ReportCardPrint";

/**
 * Non Assessment Comment — the school's own named comment slots (Report Setup →
 * Comment), filled in pupil by pupil for one class, term and sub-term. They print
 * on the report card beside the Head and PC comments.
 *
 * `adminOnly` hides the slots a PC teacher may not write, so the picker never
 * offers a grid the API would refuse.
 */
export function NonAssessmentTab({ adminOnly = true }: { adminOnly?: boolean }) {
  const { data: slots = [], isLoading } = useCommentTypes();
  const usable = (slots as any[]).filter((c) => adminOnly || !c.admin_only);
  const [slotId, setSlotId] = useState("");
  const slot = usable.find((c) => c.id === slotId);

  if (isLoading) return <div className="py-10 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></div>;
  if (usable.length === 0) {
    // Teachers' page: nothing to show rather than an admin instruction they cannot act on.
    if (!adminOnly) return null;
    return (
      <p className="text-sm text-slate-500 py-10 text-center bg-white rounded-xl border border-dashed border-slate-200">
        No comment slots yet. Add one under <b>Comment</b> (for example &ldquo;Teacher Comment&rdquo;), then fill it in here.
      </p>
    );
  }
  return (
    <div className="space-y-4">
      <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-wrap items-end gap-3">
        <div className="min-w-[220px]">
          <label className="label" htmlFor="na-slot">Comment</label>
          <select id="na-slot" value={slotId} onChange={(e) => setSlotId(e.target.value)} className="input">
            <option value="">— Select a comment —</option>
            {usable.map((c) => <option key={c.id} value={c.id}>{c.name}{c.admin_only ? " (admin only)" : ""}</option>)}
          </select>
        </div>
      </div>
      {slot ? (
        <CommentGridTab key={slot.id} kind="custom" label={slot.name} commentTypeId={slot.id} maxLength={slot.max_length} />
      ) : (
        <p className="text-sm text-slate-400 py-10 text-center bg-white rounded-xl border border-dashed border-slate-200">Choose a comment to enter it for a class.</p>
      )}
    </div>
  );
}

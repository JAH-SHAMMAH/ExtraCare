"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { BookOpen, Info, Search, X, ArrowLeft, ArrowRight, Lightbulb } from "lucide-react";
import { useAuthStore } from "@/lib/store";
import { GUIDE_TOPICS, searchTopics, type GuideTopic } from "@/lib/quickGuide";

/** Admin-only. Teachers, parents and students never get the button. */
export function QuickGuideButton() {
  const activeRole = useAuthStore((s) => s.activeRole);
  const [open, setOpen] = useState(false);
  if (activeRole && activeRole !== "admin") return null;
  return (
    <>
      <button className="btn-primary gap-2 text-xs py-1.5" onClick={() => setOpen(true)}>
        <Info size={13} /> Quick Guide
      </button>
      {open && <QuickGuideModal onClose={() => setOpen(false)} />}
    </>
  );
}

export function QuickGuideModal({ onClose }: { onClose: () => void }) {
  const [q, setQ] = useState("");
  const [topic, setTopic] = useState<GuideTopic | null>(null);
  const topics = useMemo(() => searchTopics(q), [q]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const categories = Array.from(new Set(topics.map((t) => t.category)));

  return (
    <div className="fixed inset-0 z-[60] flex items-start justify-center bg-slate-900/50 p-0 sm:p-6 overflow-y-auto" role="dialog" aria-label="Quick Guide" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="bg-white w-full max-w-3xl sm:rounded-2xl shadow-2xl overflow-hidden my-0 sm:my-6 min-h-screen sm:min-h-0">
        <div className="bg-brand-700 text-white px-5 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <BookOpen size={18} />
            <h2 className="text-lg font-bold">ExtraCare Quick Guide</h2>
          </div>
          <button onClick={onClose} aria-label="Close guide" className="p-1 rounded hover:bg-white/10"><X size={18} /></button>
        </div>

        {topic ? (
          <div className="p-5 sm:p-6">
            <button onClick={() => setTopic(null)} className="text-sm font-semibold text-brand-700 flex items-center gap-1.5 mb-4">
              <ArrowLeft size={14} /> All topics
            </button>
            <p className="text-[11px] font-bold uppercase tracking-widest text-slate-400">{topic.category}</p>
            <h3 className="text-xl font-black text-slate-900 mt-1">{topic.title}</h3>
            <p className="text-sm text-slate-500 mt-1">{topic.summary}</p>
            <ol className="mt-5 space-y-3">
              {topic.steps.map((s, i) => (
                <li key={i} className="flex gap-3">
                  <span className="shrink-0 w-6 h-6 rounded-full bg-brand-50 text-brand-700 text-xs font-bold flex items-center justify-center">{i + 1}</span>
                  <p className="text-sm text-slate-700 leading-relaxed">{s}</p>
                </li>
              ))}
            </ol>
            {topic.tips && topic.tips.length > 0 && (
              <div className="mt-5 rounded-xl bg-amber-50 border border-amber-100 p-4 space-y-2">
                {topic.tips.map((t, i) => (
                  <p key={i} className="text-sm text-amber-900 flex gap-2"><Lightbulb size={15} className="shrink-0 mt-0.5" />{t}</p>
                ))}
              </div>
            )}
            {topic.href && (
              <Link href={topic.href} onClick={onClose} className="btn-primary gap-2 mt-6 inline-flex">
                {topic.hrefLabel ?? "Open page"} <ArrowRight size={14} />
              </Link>
            )}
          </div>
        ) : (
          <div className="p-5 sm:p-6">
            <div className="relative mb-5">
              <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder={`Search ${GUIDE_TOPICS.length} guides, e.g. "attendance", "reset password"`}
                className="input pl-9 w-full"
                autoFocus
              />
            </div>
            {topics.length === 0 && <p className="text-sm text-slate-400 text-center py-10">No guide matches &ldquo;{q}&rdquo;.</p>}
            {categories.map((c) => (
              <div key={c} className="mb-5">
                <p className="text-[11px] font-bold uppercase tracking-widest text-slate-400 mb-2">{c}</p>
                <div className="space-y-2">
                  {topics.filter((t) => t.category === c).map((t) => (
                    <button key={t.id} onClick={() => setTopic(t)} className="w-full text-left rounded-xl border border-slate-200 hover:border-brand-300 hover:bg-brand-50/30 p-4 transition-colors">
                      <p className="font-semibold text-slate-900 text-sm">{t.title}</p>
                      <p className="text-xs text-slate-500 mt-1">{t.summary} <span className="text-brand-700 font-semibold">Read more</span></p>
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

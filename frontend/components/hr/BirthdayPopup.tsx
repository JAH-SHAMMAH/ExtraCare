"use client";

import { useEffect, useState } from "react";
import { Cake, X } from "lucide-react";
import { useHrBirthdays } from "@/hooks/useHrm";

/**
 * One-shot birthday greeting modal.
 *
 * Shown on dashboard mount when at least one staff/student has a birthday
 * today. Dismissal is persisted per-day in localStorage so the user sees
 * it at most once per calendar day across reloads.
 */
export function BirthdayPopup() {
  const { data: birthdays } = useHrBirthdays();
  const [open, setOpen] = useState(false);

  const todays = (birthdays ?? []).filter((b) => b.is_today);

  useEffect(() => {
    if (todays.length === 0) return;
    const key = `hr:birthday-popup:${new Date().toISOString().slice(0, 10)}`;
    if (typeof window !== "undefined" && !localStorage.getItem(key)) {
      setOpen(true);
    }
  }, [todays.length]);

  if (!open || todays.length === 0) return null;

  const dismiss = () => {
    const key = `hr:birthday-popup:${new Date().toISOString().slice(0, 10)}`;
    try { localStorage.setItem(key, "1"); } catch {}
    setOpen(false);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={dismiss}>
      <div
        onClick={(e) => e.stopPropagation()}
        className="bg-white rounded-2xl shadow-2xl max-w-md w-full overflow-hidden"
      >
        <div className="bg-gradient-to-br from-rose-500 to-amber-500 p-5 text-white relative">
          <button
            onClick={dismiss}
            className="absolute top-3 right-3 p-1 rounded-full hover:bg-white/20"
            aria-label="Dismiss"
          >
            <X className="w-4 h-4" />
          </button>
          <Cake className="w-8 h-8 mb-2" />
          <h2 className="text-xl font-black">
            {todays.length === 1 ? "It's a birthday!" : `${todays.length} birthdays today!`}
          </h2>
          <p className="text-sm opacity-90">Wish them a wonderful day.</p>
        </div>
        <ul className="divide-y divide-slate-100 max-h-72 overflow-auto">
          {todays.map((b, i) => (
            <li key={i} className="p-4 flex items-center justify-between">
              <div>
                <p className="text-sm font-bold text-slate-900">{b.name}</p>
                <p className="text-[11px] text-slate-500 capitalize">{b.role}</p>
              </div>
              <span className="text-lg">🎂</span>
            </li>
          ))}
        </ul>
        <div className="p-4 border-t border-slate-100 flex justify-end">
          <button
            onClick={dismiss}
            className="text-sm font-semibold text-slate-600 hover:text-slate-900"
          >
            Got it
          </button>
        </div>
      </div>
    </div>
  );
}

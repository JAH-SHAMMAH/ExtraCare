"use client";

import { Cake, Calendar } from "lucide-react";
import { useHrBirthdays, useHrEvents } from "@/hooks/useHrm";

/**
 * Side-panel pair of "what's happening with the people" cards: upcoming
 * birthdays + upcoming events. Used by the main `/dashboard` now; previously
 * lived on the HRM page. Same data hooks, so the two surfaces stay in sync.
 */
export function PeoplePulse({ variant = "stacked" }: { variant?: "stacked" | "split" }) {
  const { data: birthdays = [] } = useHrBirthdays();
  const { data: events = [] } = useHrEvents({ upcoming_only: true, limit: 5 });

  const wrapperClass =
    variant === "split" ? "grid lg:grid-cols-2 gap-4" : "space-y-4";

  return (
    <div className={wrapperClass}>
      <Panel title="Upcoming Birthdays" icon={Cake}>
        {birthdays.length === 0 ? (
          <Empty text="No birthdays this month." />
        ) : (
          <ul className="divide-y divide-slate-100">
            {birthdays.slice(0, 8).map((b, i) => (
              <li key={i} className="py-2 flex items-center justify-between">
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-slate-800 truncate">{b.name}</p>
                  <p className="text-[11px] text-slate-500 capitalize">{b.role}</p>
                </div>
                <span
                  className={
                    b.is_today
                      ? "text-xs font-bold text-rose-600 bg-rose-50 px-2 py-0.5 rounded-full shrink-0"
                      : "text-xs text-slate-500 shrink-0"
                  }
                >
                  {b.is_today ? "Today" : formatDay(b.date_of_birth)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <Panel title="Upcoming Events" icon={Calendar}>
        {events.length === 0 ? (
          <Empty text="No upcoming events." />
        ) : (
          <ul className="divide-y divide-slate-100">
            {events.map((e) => (
              <li key={e.id} className="py-2">
                <p className="text-sm font-semibold text-slate-800 truncate">{e.title}</p>
                <p className="text-[11px] text-slate-500">
                  {formatDateTime(e.starts_at)}
                  {e.location ? ` • ${e.location}` : ""}
                  {e.category ? ` • ${e.category}` : ""}
                </p>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}

function Panel({
  title, icon: Icon, children,
}: { title: string; icon: any; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5">
      <header className="flex items-center gap-2 mb-3">
        <Icon className="w-4 h-4 text-brand-600" />
        <h3 className="text-sm font-bold text-slate-800">{title}</h3>
      </header>
      {children}
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return <p className="text-sm text-slate-500 italic py-6 text-center">{text}</p>;
}

function formatDay(iso: string) {
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function formatDateTime(iso: string) {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

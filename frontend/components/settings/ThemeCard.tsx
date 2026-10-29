"use client";

import { useEffect, useState } from "react";
import { Moon, Sun, Monitor } from "lucide-react";
import { applyTheme, getStoredTheme, setTheme, type ThemeChoice } from "@/lib/theme";

export function ThemeCard() {
  const [choice, setChoice] = useState<ThemeChoice>("light");
  useEffect(() => {
    setChoice(getStoredTheme());
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => getStoredTheme() === "system" && applyTheme("system");
    mq.addEventListener?.("change", onChange);
    return () => mq.removeEventListener?.("change", onChange);
  }, []);

  const dark = choice === "dark";
  const pick = (c: ThemeChoice) => { setChoice(c); setTheme(c); };

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-6">
      <h2 className="text-sm font-bold text-slate-800 mb-1 flex items-center gap-2">
        {dark ? <Moon size={15} /> : <Sun size={15} />} Appearance
      </h2>
      <p className="text-xs text-slate-500 mb-4">Choose light or dark mode. It applies to every page, on this device.</p>

      <div className="flex items-center justify-between py-2">
        <div>
          <p className="text-sm font-semibold text-slate-800">Dark mode</p>
          <p className="text-xs text-slate-500">Easier on the eyes at night.</p>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={dark}
          aria-label="Dark mode"
          onClick={() => pick(dark ? "light" : "dark")}
          className={`relative inline-flex h-8 w-14 shrink-0 items-center rounded-full transition-colors ${dark ? "bg-brand-600" : "bg-slate-300"}`}
        >
          <span className={`inline-block h-6 w-6 rounded-full bg-white shadow transition-transform ${dark ? "translate-x-7" : "translate-x-1"}`} />
        </button>
      </div>

      <div className="mt-3 grid grid-cols-3 gap-2">
        {([["light", "Light", Sun], ["dark", "Dark", Moon], ["system", "Match device", Monitor]] as const).map(([v, label, Icon]) => (
          <button
            key={v}
            type="button"
            onClick={() => pick(v)}
            className={`flex flex-col items-center gap-1 rounded-lg border px-2 py-3 text-xs font-semibold transition-colors ${
              choice === v ? "border-brand-600 text-brand-700 ring-2 ring-brand-500/30" : "border-slate-200 text-slate-600 hover:bg-slate-50"
            }`}
          >
            <Icon size={20} strokeWidth={2.2} /> {label}
          </button>
        ))}
      </div>
    </div>
  );
}

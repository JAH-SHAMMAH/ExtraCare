"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Search, X, Users2, GraduationCap, Heart, Briefcase, Loader2 } from "lucide-react";
import { useGlobalSearch } from "@/hooks/useSearch";
import { cn } from "@/lib/utils";

const MODULE_ICONS: Record<string, any> = {
  users: Users2,
  students: GraduationCap,
  teachers: GraduationCap,
  patients: Heart,
  doctors: Heart,
  employees: Briefcase,
};

const MODULE_ROUTES: Record<string, string> = {
  users: "/dashboard/users",
  students: "/dashboard/modules/school/students",
  teachers: "/dashboard/modules/school/teachers",
};

export function GlobalSearch() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const router = useRouter();

  const { data: results, isLoading } = useGlobalSearch(query);

  // Keyboard shortcut: Ctrl+K or Cmd+K
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen(true);
        setTimeout(() => inputRef.current?.focus(), 50);
      }
      if (e.key === "Escape") {
        setOpen(false);
        setQuery("");
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Click outside
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  const handleSelect = useCallback((item: any) => {
    const route = MODULE_ROUTES[item.module];
    if (route) {
      router.push(`${route}?search=${encodeURIComponent(item.label)}`);
    }
    setOpen(false);
    setQuery("");
  }, [router]);

  const items = Array.isArray(results) ? results : results?.items || [];

  return (
    <div ref={containerRef} className="relative">
      <button
        onClick={() => { setOpen(true); setTimeout(() => inputRef.current?.focus(), 50); }}
        className="flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-500 text-sm transition-colors"
      >
        <Search size={14} />
        <span className="hidden md:inline">Search...</span>
        <kbd className="hidden md:inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-mono bg-white border border-slate-200 text-slate-400">
          Ctrl K
        </kbd>
      </button>

      {open && (
        <>
          {/* Backdrop */}
          <div className="fixed inset-0 bg-black/20 z-40" />

          {/* Search modal */}
          <div className="fixed top-[20%] left-1/2 -translate-x-1/2 w-full max-w-lg z-50">
            <div className="bg-white rounded-xl border border-slate-200 shadow-2xl overflow-hidden">
              {/* Input */}
              <div className="flex items-center gap-3 px-4 border-b border-slate-100">
                <Search size={16} className="text-slate-400 shrink-0" />
                <input
                  ref={inputRef}
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search students, patients, employees, users..."
                  className="flex-1 py-3.5 text-sm outline-none bg-transparent"
                  autoFocus
                />
                {query && (
                  <button onClick={() => setQuery("")} className="text-slate-400 hover:text-slate-600">
                    <X size={14} />
                  </button>
                )}
              </div>

              {/* Results */}
              <div className="max-h-80 overflow-y-auto">
                {isLoading && query.length >= 2 && (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 size={20} className="animate-spin text-slate-400" />
                  </div>
                )}

                {!isLoading && query.length >= 2 && items.length === 0 && (
                  <div className="py-8 text-center text-sm text-slate-400">
                    No results found for &ldquo;{query}&rdquo;
                  </div>
                )}

                {!isLoading && items.length > 0 && (
                  <div className="py-2">
                    {items.map((item: any, i: number) => {
                      const Icon = MODULE_ICONS[item.module] || Users2;
                      return (
                        <button
                          key={i}
                          onClick={() => handleSelect(item)}
                          className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-slate-50 transition-colors text-left"
                        >
                          <div className="w-8 h-8 rounded-lg bg-slate-100 flex items-center justify-center shrink-0">
                            <Icon size={14} className="text-slate-500" />
                          </div>
                          <div className="min-w-0 flex-1">
                            <p className="text-sm font-medium text-slate-800 truncate">{item.label}</p>
                            <p className="text-xs text-slate-400 truncate">{item.sublabel || item.module}</p>
                          </div>
                          <span className="badge bg-slate-50 text-slate-500 border-slate-200 text-[10px]">
                            {item.module}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                )}

                {query.length < 2 && (
                  <div className="py-8 text-center text-sm text-slate-400">
                    Type at least 2 characters to search
                  </div>
                )}
              </div>

              {/* Footer */}
              <div className="px-4 py-2.5 border-t border-slate-100 flex items-center gap-4 text-[10px] text-slate-400">
                <span><kbd className="font-mono bg-slate-100 px-1 rounded">Esc</kbd> to close</span>
                <span><kbd className="font-mono bg-slate-100 px-1 rounded">Enter</kbd> to select</span>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

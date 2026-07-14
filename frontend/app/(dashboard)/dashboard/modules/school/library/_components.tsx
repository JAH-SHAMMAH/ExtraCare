"use client";

import { useMemo, useState } from "react";
import {
  BookOpen, Search, X, Loader2, Check, ArrowRight, User as UserIcon, RotateCcw, Trash2,
} from "lucide-react";
import {
  useLibraryBooks, useLibraryLoans, useCreateBook, useDeleteBook, useIssueLoan, useReturnLoan,
  useLibraryCategories, useLibraryLocations, useStudents,
  type LibraryBookRow, type LibraryLoanRow,
} from "@/hooks/useSchool";
import { useDelayedFlag } from "@/hooks/useDelayedFlag";
import { TableSkeleton, Skeleton } from "@/components/loading/Skeleton";
import { cn, formatDate } from "@/lib/utils";

// ── Stats ────────────────────────────────────────────────────────────────────

export function StatCard({
  label, value, color, icon: Icon, highlight = false,
}: { label: string; value: number | string; color: string; icon: typeof BookOpen; highlight?: boolean }) {
  return (
    <div className={cn("bg-white rounded-xl border p-4 flex items-center gap-3", highlight ? "border-rose-300" : "border-slate-200")}>
      <div className={cn("w-10 h-10 rounded-lg flex items-center justify-center shrink-0", color)}><Icon size={16} /></div>
      <div>
        <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500">{label}</p>
        <p className="text-xl font-black text-slate-900 tabular-nums">{value}</p>
      </div>
    </div>
  );
}

// ── Catalogue (browse / manage) ────────────────────────────────────────────────

export function CatalogueTab({ onIssue, manage = false }: { onIssue: (book: LibraryBookRow) => void; manage?: boolean }) {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState<string | undefined>(undefined);
  const [availableOnly, setAvailableOnly] = useState(false);

  const { data, isLoading } = useLibraryBooks({ search: search || undefined, category, available_only: availableOnly || undefined });
  const showSkeleton = useDelayedFlag(isLoading);
  const books = data?.items ?? [];
  const categories = data?.categories ?? [];
  const deleteBook = useDeleteBook();

  return (
    <>
      <div className="bg-white rounded-xl border border-slate-200 p-3 mb-4 flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-64">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search by title, author, ISBN…" className="input pl-9" />
        </div>
        <select value={category ?? ""} onChange={(e) => setCategory(e.target.value || undefined)} className="input max-w-[200px]">
          <option value="">All categories</option>
          {categories.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <label className="flex items-center gap-2 text-xs font-semibold text-slate-600 select-none cursor-pointer">
          <input type="checkbox" checked={availableOnly} onChange={(e) => setAvailableOnly(e.target.checked)} className="rounded border-slate-300 text-brand-600 focus:ring-brand-500" />
          Available only
        </label>
      </div>

      {showSkeleton ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="bg-white rounded-xl border border-slate-200 p-4 space-y-3">
              <Skeleton className="h-24 w-full rounded-lg" /><Skeleton className="h-3 w-3/4" /><Skeleton className="h-3 w-1/2" />
            </div>
          ))}
        </div>
      ) : books.length === 0 ? (
        <EmptyState title="No books match" subtitle="Try a different search or add a new book." />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {books.map((b) => (
            <BookCard key={b.id} book={b} manage={manage} onIssue={() => onIssue(b)}
              onDelete={() => { if (confirm(`Remove "${b.title}" from the catalogue?`)) deleteBook.mutate(b.id); }} />
          ))}
        </div>
      )}
    </>
  );
}

function BookCard({ book, onIssue, onDelete, manage }: { book: LibraryBookRow; onIssue: () => void; onDelete: () => void; manage: boolean }) {
  const available = book.available_copies > 0;
  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden hover:shadow-md transition-shadow group">
      <div className={cn("h-24 flex items-center justify-center border-b", available ? "bg-gradient-to-br from-brand-50 to-indigo-50 border-brand-100" : "bg-slate-50 border-slate-100")}>
        <BookOpen size={32} className={available ? "text-brand-600" : "text-slate-400"} />
      </div>
      <div className="p-4">
        <div className="flex items-start justify-between gap-2 mb-2">
          {book.category && <span className="badge bg-slate-100 text-slate-600 border-slate-200 text-[9px]">{book.category}</span>}
          <span className={cn("badge text-[9px]", available ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-rose-50 text-rose-700 border-rose-200")}>
            {available ? `${book.available_copies}/${book.total_copies} available` : "All out"}
          </span>
        </div>
        <p className="text-sm font-bold text-slate-900 line-clamp-2 leading-tight mb-1">{book.title}</p>
        <p className="text-xs text-slate-500 truncate">{book.author}</p>
        <p className="text-[10px] text-slate-400 mt-1">{[book.publication_year, book.shelf_location ? `Shelf ${book.shelf_location}` : null].filter(Boolean).join(" · ")}</p>
        <div className="flex gap-2 mt-3">
          <button onClick={onIssue} disabled={!available} className={cn("flex-1 btn-primary text-xs py-1.5", !available && "opacity-50 cursor-not-allowed")}>Issue</button>
          {manage && (
            <button onClick={onDelete} className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 opacity-0 group-hover:opacity-100 transition-opacity" title="Remove from catalogue"><Trash2 size={14} /></button>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Loans ──────────────────────────────────────────────────────────────────────

export function LoansTab() {
  const [filter, setFilter] = useState<"all" | "borrowed" | "overdue" | "returned">("all");
  const { data, isLoading } = useLibraryLoans({ status: filter === "all" ? undefined : filter, page_size: 100 });
  const showSkeleton = useDelayedFlag(isLoading);
  const returnLoan = useReturnLoan();
  const loans = data?.items ?? [];

  return (
    <>
      <div className="bg-white rounded-xl border border-slate-200 p-1 mb-4 inline-flex">
        {[{ id: "all" as const, label: "All" }, { id: "borrowed" as const, label: "Active" }, { id: "overdue" as const, label: "Overdue" }, { id: "returned" as const, label: "Returned" }].map((f) => (
          <button key={f.id} onClick={() => setFilter(f.id)} className={cn("px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors", filter === f.id ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100")}>{f.label}</button>
        ))}
      </div>
      {showSkeleton ? <TableSkeleton rows={6} cols={5} /> : loans.length === 0 ? (
        <EmptyState title="No loans to show" subtitle="Try a different filter or issue a new book." />
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
          <table className="w-full text-left">
            <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Book", "Borrower", "Issued", "Due", "Status", ""].map((h) => <th key={h} className="px-5 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
            <tbody className="divide-y divide-slate-50">{loans.map((l) => <LoanRow key={l.id} loan={l} onReturn={() => returnLoan.mutate(l.id)} />)}</tbody>
          </table>
        </div>
      )}
    </>
  );
}

function LoanRow({ loan, onReturn }: { loan: LibraryLoanRow; onReturn: () => void }) {
  const returned = loan.status === "returned";
  return (
    <tr className={cn("hover:bg-slate-50/60 transition-colors", loan.is_overdue && "bg-rose-50/30")}>
      <td className="px-5 py-3.5"><p className="text-sm font-bold text-slate-900 line-clamp-1">{loan.book_title ?? "—"}</p><p className="text-xs text-slate-500">{loan.book_author ?? ""}</p></td>
      <td className="px-5 py-3.5"><p className="text-sm font-medium text-slate-800 line-clamp-1">{loan.borrower_name ?? "—"}</p><p className="text-xs text-slate-500 line-clamp-1">{loan.borrower_email}</p></td>
      <td className="px-5 py-3.5 text-xs text-slate-500 tabular-nums">{formatDate(loan.borrowed_at)}</td>
      <td className="px-5 py-3.5 text-xs tabular-nums"><span className={cn(loan.is_overdue ? "text-rose-700 font-bold" : "text-slate-600")}>{loan.due_date}</span></td>
      <td className="px-5 py-3.5">
        {returned ? <span className="badge bg-slate-100 text-slate-600 border-slate-200 text-[10px]">Returned</span>
          : loan.is_overdue ? <span className="badge bg-rose-50 text-rose-700 border-rose-200 text-[10px]">Overdue</span>
            : <span className="badge bg-emerald-50 text-emerald-700 border-emerald-200 text-[10px]">Active</span>}
      </td>
      <td className="px-5 py-3.5">{!returned && <button onClick={onReturn} className="text-xs font-semibold text-brand-600 hover:text-brand-700 flex items-center gap-1"><RotateCcw size={12} /> Return</button>}</td>
    </tr>
  );
}

// ── Add book drawer (uses managed categories + locations as picklists) ──────────

export function AddBookDrawer({ onClose }: { onClose: () => void }) {
  const [form, setForm] = useState({ title: "", author: "", category: "", publisher: "", publication_year: "", isbn: "", shelf_location: "", total_copies: 1, description: "" });
  const create = useCreateBook();
  const { data: categories = [] } = useLibraryCategories();
  const { data: locations = [] } = useLibraryLocations();

  const save = async () => {
    await create.mutateAsync({ ...form, publication_year: form.publication_year ? Number(form.publication_year) : undefined, total_copies: Number(form.total_copies) || 1 });
    onClose();
  };

  return (
    <DrawerShell title="Add a book" subtitle="Catalogue a new title" onClose={onClose}>
      <div className="space-y-4 p-6">
        <div><label className="label">Title *</label><input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className="input" /></div>
        <div><label className="label">Author *</label><input value={form.author} onChange={(e) => setForm({ ...form, author: e.target.value })} className="input" /></div>
        <div className="grid grid-cols-2 gap-3">
          <div><label className="label">Category</label>
            <input list="lib-cats" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} placeholder="Fiction, Science…" className="input" />
            <datalist id="lib-cats">{categories.map((c) => <option key={c.id} value={c.name} />)}</datalist>
          </div>
          <div><label className="label">Shelf</label>
            <input list="lib-locs" value={form.shelf_location} onChange={(e) => setForm({ ...form, shelf_location: e.target.value })} placeholder="A1-12" className="input" />
            <datalist id="lib-locs">{locations.map((l) => <option key={l.id} value={l.code || l.name} />)}</datalist>
          </div>
          <div><label className="label">Total copies</label><input type="number" min={1} value={form.total_copies} onChange={(e) => setForm({ ...form, total_copies: Number(e.target.value) })} className="input" /></div>
          <div><label className="label">Year</label><input type="number" min={1800} max={2100} value={form.publication_year} onChange={(e) => setForm({ ...form, publication_year: e.target.value })} className="input" /></div>
          <div className="col-span-2"><label className="label">Publisher</label><input value={form.publisher} onChange={(e) => setForm({ ...form, publisher: e.target.value })} className="input" /></div>
          <div className="col-span-2"><label className="label">ISBN</label><input value={form.isbn} onChange={(e) => setForm({ ...form, isbn: e.target.value })} className="input" /></div>
        </div>
      </div>
      <div className="sticky bottom-0 bg-white border-t border-slate-200 px-6 py-4 flex items-center justify-end gap-2">
        <button onClick={onClose} className="btn-secondary">Cancel</button>
        <button onClick={save} disabled={create.isPending || !form.title.trim() || !form.author.trim()} className="btn-primary gap-2">
          {create.isPending ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />} Add to catalogue
        </button>
      </div>
    </DrawerShell>
  );
}

// ── Issue loan drawer ────────────────────────────────────────────────────────

export function IssueLoanDrawer({ book, onClose }: { book: LibraryBookRow; onClose: () => void }) {
  const [borrower, setBorrower] = useState<{ user_id: string; label: string } | null>(null);
  const [search, setSearch] = useState("");
  const { data: students } = useStudents({ page_size: 50, search: search || undefined });
  const defaultDue = useMemo(() => { const d = new Date(); d.setDate(d.getDate() + 14); return d.toISOString().slice(0, 10); }, []);
  const [dueDate, setDueDate] = useState(defaultDue);
  const issue = useIssueLoan();

  const matches = ((students?.items ?? []) as Array<{ id: string; first_name: string; last_name: string; user_id?: string | null; student_id: string }>).filter((s) => !!s.user_id);

  const submit = async () => {
    if (!borrower) return;
    await issue.mutateAsync({ book_id: book.id, borrower_user_id: borrower.user_id, due_date: dueDate });
    onClose();
  };

  return (
    <DrawerShell title="Issue book" subtitle={book.title} onClose={onClose}>
      <div className="p-6 space-y-5">
        <div className="flex items-center gap-3 p-3 rounded-xl bg-slate-50 border border-slate-100">
          <div className="w-10 h-10 rounded-lg bg-brand-50 text-brand-700 flex items-center justify-center"><BookOpen size={15} /></div>
          <div className="min-w-0 flex-1"><p className="text-sm font-bold text-slate-900 truncate">{book.title}</p><p className="text-xs text-slate-500 truncate">{book.author} · {book.available_copies} of {book.total_copies} available</p></div>
        </div>
        <div>
          <label className="label">Borrower *</label>
          {borrower ? (
            <div className="flex items-center gap-2 p-2 rounded-lg border border-brand-200 bg-brand-50">
              <UserIcon size={14} className="text-brand-600" /><span className="text-sm font-semibold text-brand-800 flex-1">{borrower.label}</span>
              <button onClick={() => setBorrower(null)} className="text-brand-600 hover:text-brand-800"><X size={14} /></button>
            </div>
          ) : (
            <>
              <div className="relative"><Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search student by name or ID…" className="input pl-9" /></div>
              {search && matches.length > 0 && (
                <div className="mt-2 rounded-lg border border-slate-200 max-h-52 overflow-y-auto divide-y divide-slate-50">
                  {matches.slice(0, 10).map((s) => (
                    <button key={s.id} onClick={() => { setBorrower({ user_id: s.user_id!, label: `${s.first_name} ${s.last_name} (${s.student_id})` }); setSearch(""); }} className="w-full text-left px-3 py-2 hover:bg-slate-50 text-sm text-slate-700">
                      <span className="font-semibold">{s.first_name} {s.last_name}</span><span className="text-slate-400 ml-2">· {s.student_id}</span>
                    </button>
                  ))}
                </div>
              )}
              {search && matches.length === 0 && <p className="text-xs text-slate-400 mt-1">No students match.</p>}
            </>
          )}
        </div>
        <div>
          <label className="label">Due date *</label>
          <input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} min={new Date().toISOString().slice(0, 10)} className="input" />
          <p className="text-[10px] text-slate-400 mt-1">Default is 2 weeks from today.</p>
        </div>
      </div>
      <div className="sticky bottom-0 bg-white border-t border-slate-200 px-6 py-4 flex items-center justify-end gap-2">
        <button onClick={onClose} className="btn-secondary">Cancel</button>
        <button onClick={submit} disabled={!borrower || issue.isPending} className="btn-primary gap-2">{issue.isPending ? <Loader2 size={14} className="animate-spin" /> : <ArrowRight size={14} />} Issue book</button>
      </div>
    </DrawerShell>
  );
}

export function DrawerShell({ title, subtitle, onClose, children }: { title: string; subtitle?: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex">
      <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm animate-fade-in" onClick={onClose} />
      <div className="relative ml-auto w-full max-w-lg bg-white shadow-2xl overflow-y-auto animate-slide-in flex flex-col">
        <div className="sticky top-0 z-10 bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between">
          <div className="min-w-0"><p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">{title}</p>{subtitle && <h2 className="text-lg font-black text-slate-900 truncate">{subtitle}</h2>}</div>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-slate-100 text-slate-500"><X size={18} /></button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function EmptyState({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-12 text-center">
      <div className="w-14 h-14 rounded-2xl bg-slate-100 flex items-center justify-center mx-auto mb-4"><BookOpen size={26} className="text-slate-400" /></div>
      <h2 className="text-base font-bold text-slate-800 mb-1">{title}</h2>
      <p className="text-sm text-slate-500 max-w-md mx-auto">{subtitle}</p>
    </div>
  );
}

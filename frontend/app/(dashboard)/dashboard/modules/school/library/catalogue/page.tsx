"use client";

import { useState } from "react";
import { BookPlus } from "lucide-react";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { type LibraryBookRow } from "@/hooks/useSchool";
import { CatalogueTab, AddBookDrawer, IssueLoanDrawer } from "../_components";

/** Library — Manage Catalogue. Full book management: add, remove, issue. */
export default function ManageCataloguePage() {
  const canWrite = useHasPermission("school:library:write");
  const [addOpen, setAddOpen] = useState(false);
  const [issueTarget, setIssueTarget] = useState<LibraryBookRow | null>(null);

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="flex items-end justify-between gap-4 mb-6">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Education</span><span>/</span><span>Library</span><span>/</span><span className="text-brand-600 font-semibold">Manage Catalogue</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Manage Catalogue</h1>
          <p className="text-slate-500 text-sm mt-0.5">Add, edit and remove titles in the collection.</p>
        </div>
        {canWrite && <button onClick={() => setAddOpen(true)} className="btn-primary gap-2"><BookPlus size={15} /> New Book Catalogue</button>}
      </div>

      <CatalogueTab manage={canWrite} onIssue={(book) => setIssueTarget(book)} />
      {addOpen && <AddBookDrawer onClose={() => setAddOpen(false)} />}
      {issueTarget && <IssueLoanDrawer book={issueTarget} onClose={() => setIssueTarget(null)} />}
    </div>
  );
}

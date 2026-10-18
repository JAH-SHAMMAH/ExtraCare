"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, RotateCcw } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";

export default function DeletedUsersPage() {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const { data, isLoading } = useQuery({ queryKey: ["users-deleted"], queryFn: () => api.get("/users/deleted").then((r) => r.data as { items: any[] }) });
  const restore = useMutation({
    mutationFn: (id: string) => api.post(`/users/${id}/restore`).then((r) => r.data),
    onSuccess: () => { toast.success("User restored."); qc.invalidateQueries({ queryKey: ["users-deleted"] }); },
    onError: (e: any) => toast.error(typeof e?.response?.data?.detail === "string" ? e.response.data.detail : "Could not restore."),
  });
  const rows = (data?.items ?? []).filter((u) => !q || `${u.full_name} ${u.email}`.toLowerCase().includes(q.toLowerCase()));
  return (
    <div className="p-4 sm:p-8 max-w-4xl mx-auto">
      <h1 className="text-2xl font-black text-slate-900 tracking-tight mb-4">Manage Deleted Users</h1>
      <input className="input max-w-xs mb-3" placeholder="Search" value={q} onChange={(e) => setQ(e.target.value)} />
      {isLoading ? <Loader2 className="animate-spin text-slate-400 mx-auto my-8" /> : (
        <div className="bg-white border border-slate-200 rounded-xl overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="text-left text-xs uppercase text-slate-500 bg-slate-50"><th className="p-2">Name</th><th className="p-2">Email</th><th className="p-2">Deleted</th><th className="p-2" /></tr></thead>
            <tbody>
              {rows.map((u) => (
                <tr key={u.id} className="border-t">
                  <td className="p-2">{u.full_name}</td><td className="p-2">{u.email}</td>
                  <td className="p-2">{u.deleted_at ? new Date(u.deleted_at).toLocaleDateString() : ""}</td>
                  <td className="p-2 text-right"><button onClick={() => restore.mutate(u.id)} className="btn-secondary gap-1"><RotateCcw size={14} /> Restore</button></td>
                </tr>
              ))}
              {!rows.length && <tr><td colSpan={4} className="p-6 text-center text-slate-400">No deleted users.</td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

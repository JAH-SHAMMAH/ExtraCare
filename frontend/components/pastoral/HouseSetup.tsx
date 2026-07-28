"use client";

import { useState } from "react";
import {
  useHouses, useCreateHouse, useUpdateHouse, useDeleteHouse, useSections,
} from "@/hooks/usePlatform";
import {
  useHouseMasters, useAddHouseMaster, useRemoveHouseMaster,
  useHouseWeeks, useCreateHouseWeek, useUpdateHouseWeek, useDeleteHouseWeek,
} from "@/hooks/usePastoral";
import { EntityPicker } from "@/components/inputs/EntityPicker";
import { cn } from "@/lib/utils";
import { Plus, Trash2, Loader2, Check, Power } from "lucide-react";
import type { SchoolSection } from "@/types";

type Sub = "management" | "masters" | "weeks";

export function HouseSetup({ canWrite }: { canWrite: boolean }) {
  const [sub, setSub] = useState<Sub>("management");
  return (
    <div>
      <div className="flex gap-1 mb-4">
        {([["management", "House Management"], ["masters", "House Masters"], ["weeks", "House Week Management"]] as [Sub, string][]).map(([k, l]) => (
          <button key={k} onClick={() => setSub(k)} className={cn("px-3 py-1.5 text-xs font-semibold rounded-lg transition", sub === k ? "bg-brand-50 text-brand-700 border border-brand-200" : "text-slate-500 hover:bg-slate-50")}>{l}</button>
        ))}
      </div>
      {sub === "management" ? <Management canWrite={canWrite} /> : sub === "masters" ? <Masters canWrite={canWrite} /> : <Weeks canWrite={canWrite} />}
    </div>
  );
}

function Management({ canWrite }: { canWrite: boolean }) {
  const { data: houses = [], isLoading } = useHouses();
  const { data: sections = [] } = useSections();
  const create = useCreateHouse();
  const update = useUpdateHouse();
  const del = useDeleteHouse();
  const [f, setF] = useState({ name: "", color: "#3b82f6", section_id: "" });

  return (
    <div className="space-y-4">
      {canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-wrap items-end gap-3">
          <div><label className="label">House name</label><input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} className="input" placeholder="e.g. Red House" /></div>
          <div><label className="label">Color</label><input type="color" value={f.color} onChange={(e) => setF({ ...f, color: e.target.value })} className="input h-10 w-16 p-1" /></div>
          <div><label className="label">School</label>
            <select value={f.section_id} onChange={(e) => setF({ ...f, section_id: e.target.value })} className="input w-auto min-w-[150px]">
              <option value="">All schools</option>
              {(sections as SchoolSection[]).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
          <button onClick={() => f.name.trim() && create.mutate({ name: f.name.trim(), color: f.color, section_id: f.section_id || null }, { onSuccess: () => setF({ name: "", color: "#3b82f6", section_id: "" }) })} disabled={!f.name.trim() || create.isPending} className="btn-primary gap-2"><Plus size={15} /> Add New House</button>
        </div>
      )}
      {isLoading ? <div className="py-10 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></div>
        : houses.length === 0 ? <p className="text-sm text-slate-400 py-6 text-center bg-white rounded-xl border border-slate-200">No houses yet.</p>
        : (
          <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
            {houses.map((h: any) => (
              <div key={h.id} className="flex items-center gap-3 px-4 py-3">
                <span className="w-6 h-6 rounded shrink-0 border border-slate-200" style={{ background: h.color || "#cbd5e1" }} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-slate-800">{h.name}</p>
                  <p className="text-xs text-slate-400">{h.section_name || "All schools"}</p>
                </div>
                <span className={cn("badge", h.is_active ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-50 text-slate-400 border-slate-200")}>{h.is_active ? "Active" : "Inactive"}</span>
                {canWrite && <>
                  <button onClick={() => update.mutate({ id: h.id, data: { is_active: !h.is_active } })} title={h.is_active ? "Deactivate" : "Activate"} className="text-slate-400 hover:text-amber-600 p-1"><Power size={15} /></button>
                  <button onClick={() => { if (confirm(`Delete ${h.name}?`)) del.mutate(h.id); }} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={15} /></button>
                </>}
              </div>
            ))}
          </div>
        )}
    </div>
  );
}

function Masters({ canWrite }: { canWrite: boolean }) {
  const { data: houses = [] } = useHouses();
  const [houseId, setHouseId] = useState("");
  const { data: masters = [], isLoading } = useHouseMasters(houseId || undefined);
  const add = useAddHouseMaster();
  const remove = useRemoveHouseMaster();
  const [userId, setUserId] = useState("");

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-3">
        <div><label className="label">House</label>
          <select value={houseId} onChange={(e) => setHouseId(e.target.value)} className="input max-w-xs">
            <option value="">All houses</option>
            {houses.map((h: any) => <option key={h.id} value={h.id}>{h.name}</option>)}
          </select>
        </div>
        {canWrite && houseId && (
          <div className="flex items-end gap-3">
            <div className="flex-1 max-w-sm"><label className="label">Add master (staff)</label><EntityPicker type="staff" value={userId || null} onChange={(id) => setUserId(id || "")} /></div>
            <button onClick={() => userId && add.mutate({ house_id: houseId, user_id: userId }, { onSuccess: () => setUserId("") })} disabled={!userId || add.isPending} className="btn-primary gap-2"><Plus size={15} /> Add</button>
          </div>
        )}
      </div>
      {isLoading ? <div className="py-10 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></div>
        : masters.length === 0 ? <p className="text-sm text-slate-400 py-6 text-center bg-white rounded-xl border border-slate-200">No house masters{houseId ? " for this house" : ""} yet.</p>
        : (
          <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
            {masters.map((m: any) => (
              <div key={m.id} className="flex items-center gap-3 px-4 py-3">
                <div className="flex-1"><p className="text-sm font-semibold text-slate-800">{m.user_name}</p><p className="text-xs text-slate-400">{m.house_name}</p></div>
                {canWrite && <button onClick={() => remove.mutate(m.id)} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={15} /></button>}
              </div>
            ))}
          </div>
        )}
    </div>
  );
}

function Weeks({ canWrite }: { canWrite: boolean }) {
  const { data: weeks = [], isLoading } = useHouseWeeks();
  const create = useCreateHouseWeek();
  const update = useUpdateHouseWeek();
  const del = useDeleteHouseWeek();
  const [f, setF] = useState({ name: "", start_date: "", end_date: "" });

  return (
    <div className="space-y-4">
      {canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[160px]"><label className="label">Week name</label><input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} className="input" placeholder="e.g. Week 1" /></div>
          <div><label className="label">Start</label><input type="date" value={f.start_date} onChange={(e) => setF({ ...f, start_date: e.target.value })} className="input" /></div>
          <div><label className="label">End</label><input type="date" value={f.end_date} onChange={(e) => setF({ ...f, end_date: e.target.value })} className="input" /></div>
          <button onClick={() => f.name.trim() && create.mutate({ name: f.name.trim(), start_date: f.start_date || null, end_date: f.end_date || null }, { onSuccess: () => setF({ name: "", start_date: "", end_date: "" }) })} disabled={!f.name.trim() || create.isPending} className="btn-primary gap-2"><Plus size={15} /> Add</button>
        </div>
      )}
      {isLoading ? <div className="py-10 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></div>
        : weeks.length === 0 ? <p className="text-sm text-slate-400 py-6 text-center bg-white rounded-xl border border-slate-200">No house weeks yet.</p>
        : (
          <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
            {weeks.map((w: any) => (
              <div key={w.id} className="flex items-center gap-3 px-4 py-3">
                <div className="flex-1"><p className="text-sm font-semibold text-slate-800">{w.name}</p><p className="text-xs text-slate-400">{w.start_date || "—"} → {w.end_date || "—"}</p></div>
                <span className={cn("badge", w.is_active ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-50 text-slate-400 border-slate-200")}>{w.is_active ? "Active" : "Inactive"}</span>
                {canWrite && <>
                  <button onClick={() => update.mutate({ id: w.id, data: { is_active: !w.is_active } })} className="text-slate-400 hover:text-amber-600 p-1"><Power size={15} /></button>
                  <button onClick={() => { if (confirm(`Delete ${w.name}?`)) del.mutate(w.id); }} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={15} /></button>
                </>}
              </div>
            ))}
          </div>
        )}
    </div>
  );
}

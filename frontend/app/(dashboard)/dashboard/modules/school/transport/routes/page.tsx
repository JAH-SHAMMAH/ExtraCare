"use client";

import { useState } from "react";
import Link from "next/link";
import {
  MapPin, Plus, X, Loader2, Sun, Moon, Bus, User as UserIcon,
  GripVertical, Trash2, ArrowLeft, GraduationCap, Clock,
} from "lucide-react";
import {
  useRoutes, useRoute, useCreateRoute, useDeleteRoute,
  useAddStop, useDeleteStop, useAssignStudent, useUnassignStudent,
  useVehicles, useDrivers, useCreateTrip,
  type RouteRow, type StopRow, type RosterRow,
} from "@/hooks/useTransport";
import { useStudents } from "@/hooks/useSchool";
import { useDelayedFlag } from "@/hooks/useDelayedFlag";
import { Skeleton, TableSkeleton } from "@/components/loading/Skeleton";
import { cn } from "@/lib/utils";

export default function TransportRoutesPage() {
  const { data, isLoading } = useRoutes(false);
  const showSkeleton = useDelayedFlag(isLoading);
  const [openRouteId, setOpenRouteId] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  const routes = data?.items ?? [];

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
            <Link href="/dashboard/modules/school/transport" className="hover:text-slate-600">Transport</Link>
            <span>/</span>
            <span className="text-brand-600 font-semibold">Routes</span>
          </nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Routes</h1>
          <p className="text-slate-500 text-sm mt-0.5">
            Plan stops, assign students, and dispatch trips for each school run.
          </p>
        </div>
        <button onClick={() => setShowCreate(true)} className="btn-primary gap-2">
          <Plus size={14} /> New Route
        </button>
      </div>

      {showSkeleton ? (
        <TableSkeleton rows={4} cols={4} />
      ) : routes.length === 0 ? (
        <EmptyState onCreate={() => setShowCreate(true)} />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {routes.map((r) => (
            <RouteCard key={r.id} route={r} onClick={() => setOpenRouteId(r.id)} />
          ))}
        </div>
      )}

      {showCreate && <CreateRouteDrawer onClose={() => setShowCreate(false)} />}
      {openRouteId && (
        <RouteDrawer routeId={openRouteId} onClose={() => setOpenRouteId(null)} />
      )}
    </div>
  );
}

// ── Route card ───────────────────────────────────────────────────────────────

function RouteCard({ route, onClick }: { route: RouteRow; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="text-left bg-white rounded-xl border border-slate-200 p-5 hover:shadow-md hover:border-brand-200 transition-all w-full"
    >
      <div className="flex items-center gap-3 mb-3">
        <div className="w-10 h-10 rounded-lg bg-brand-50 text-brand-700 flex items-center justify-center shrink-0">
          <MapPin size={16} />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-black text-slate-900 truncate">{route.name}</p>
          <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">
            {route.code ?? "—"}
          </p>
        </div>
        {!route.is_active && (
          <span className="badge bg-slate-100 text-slate-600 border-slate-200 text-[9px]">Inactive</span>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3 text-xs mb-3">
        <Stat label="Vehicle" value={route.vehicle?.registration_number ?? "—"} icon={Bus} />
        <Stat label="Driver" value={route.driver?.full_name ?? "—"} icon={UserIcon} />
      </div>

      <div className="flex items-center gap-3 text-xs text-slate-500">
        <span className="flex items-center gap-1">
          <Sun size={11} className="text-amber-500" /> {route.morning_start_time ?? "—"}
        </span>
        <span className="flex items-center gap-1">
          <Moon size={11} className="text-indigo-500" /> {route.afternoon_start_time ?? "—"}
        </span>
        <span className="flex items-center gap-1 ml-auto font-semibold text-slate-700">
          <GraduationCap size={11} />
          {route.student_count ?? 0} student{route.student_count === 1 ? "" : "s"}
        </span>
      </div>
    </button>
  );
}

function Stat({ label, value, icon: Icon }: { label: string; value: string; icon: typeof Bus }) {
  return (
    <div className="flex items-center gap-2">
      <Icon size={12} className="text-slate-400 shrink-0" />
      <div className="min-w-0">
        <p className="text-[9px] font-bold uppercase tracking-widest text-slate-400">{label}</p>
        <p className="text-xs font-semibold text-slate-700 truncate">{value}</p>
      </div>
    </div>
  );
}

// ── Create route drawer ──────────────────────────────────────────────────────

function CreateRouteDrawer({ onClose }: { onClose: () => void }) {
  const { data: vehicles } = useVehicles();
  const { data: drivers } = useDrivers();
  const create = useCreateRoute();

  const [form, setForm] = useState({
    name: "", code: "", description: "",
    vehicle_id: "", driver_id: "",
    morning_start_time: "06:30", afternoon_start_time: "15:15",
  });

  const submit = async () => {
    await create.mutateAsync({
      ...form,
      vehicle_id: form.vehicle_id || null,
      driver_id: form.driver_id || null,
    });
    onClose();
  };

  return (
    <DrawerShell title="New route" onClose={onClose}>
      <div className="p-6 space-y-4">
        <div>
          <label className="label">Route name *</label>
          <input
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="e.g. Northside Route"
            className="input"
          />
        </div>
        <div>
          <label className="label">Code</label>
          <input
            value={form.code}
            onChange={(e) => setForm({ ...form, code: e.target.value })}
            placeholder="e.g. RT-N1"
            className="input font-mono"
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label">Vehicle</label>
            <select
              value={form.vehicle_id}
              onChange={(e) => setForm({ ...form, vehicle_id: e.target.value })}
              className="input"
            >
              <option value="">— assign later —</option>
              {(vehicles?.items ?? []).map((v) => (
                <option key={v.id} value={v.id}>
                  {v.registration_number} ({v.capacity} seats)
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">Driver</label>
            <select
              value={form.driver_id}
              onChange={(e) => setForm({ ...form, driver_id: e.target.value })}
              className="input"
            >
              <option value="">— assign later —</option>
              {(drivers?.items ?? []).map((d) => (
                <option key={d.id} value={d.id}>{d.full_name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">Morning start</label>
            <input
              type="time"
              value={form.morning_start_time}
              onChange={(e) => setForm({ ...form, morning_start_time: e.target.value })}
              className="input"
            />
          </div>
          <div>
            <label className="label">Afternoon start</label>
            <input
              type="time"
              value={form.afternoon_start_time}
              onChange={(e) => setForm({ ...form, afternoon_start_time: e.target.value })}
              className="input"
            />
          </div>
        </div>
        <div>
          <label className="label">Description</label>
          <textarea
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            rows={2}
            className="input"
          />
        </div>
      </div>
      <div className="sticky bottom-0 bg-white border-t border-slate-200 px-6 py-4 flex items-center justify-end gap-2">
        <button onClick={onClose} className="btn-secondary">Cancel</button>
        <button
          onClick={submit}
          disabled={!form.name.trim() || create.isPending}
          className="btn-primary gap-2"
        >
          {create.isPending && <Loader2 size={14} className="animate-spin" />}
          Create route
        </button>
      </div>
    </DrawerShell>
  );
}

// ── Route detail drawer ──────────────────────────────────────────────────────

function RouteDrawer({ routeId, onClose }: { routeId: string; onClose: () => void }) {
  const { data, isLoading } = useRoute(routeId);
  const showSkeleton = useDelayedFlag(isLoading);
  const deleteRoute = useDeleteRoute();
  const createTrip = useCreateTrip();

  return (
    <DrawerShell
      title={data?.route ? `${data.route.code ?? ""} · ${data.route.name}` : "Route"}
      onClose={onClose}
      wide
    >
      {showSkeleton || !data ? (
        <div className="p-6 space-y-3">
          <Skeleton className="h-20 w-full rounded-xl" />
          <Skeleton className="h-32 w-full rounded-xl" />
        </div>
      ) : (
        <div className="p-6 space-y-6">
          {/* Quick dispatch panel */}
          <div className="bg-brand-50/50 border border-brand-100 rounded-xl p-4 flex items-center justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-widest text-brand-700">Dispatch today</p>
              <p className="text-sm text-slate-600 mt-0.5">Spawn a trip for this route now.</p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => createTrip.mutate({ route_id: routeId, direction: "morning" })}
                disabled={createTrip.isPending}
                className="btn-secondary gap-1.5 text-xs py-1.5"
              >
                <Sun size={13} /> Morning
              </button>
              <button
                onClick={() => createTrip.mutate({ route_id: routeId, direction: "afternoon" })}
                disabled={createTrip.isPending}
                className="btn-secondary gap-1.5 text-xs py-1.5"
              >
                <Moon size={13} /> Afternoon
              </button>
            </div>
          </div>

          <RouteSummary route={data.route} />
          <StopsSection routeId={routeId} stops={data.route.stops} />
          <RosterSection
            routeId={routeId}
            roster={data.roster}
            stops={data.route.stops}
          />

          <div className="border-t border-slate-100 pt-4">
            <button
              onClick={() => {
                if (confirm(`Remove "${data.route.name}"? Existing trips will stay in history.`)) {
                  deleteRoute.mutate(routeId);
                  onClose();
                }
              }}
              className="text-xs font-semibold text-rose-600 hover:text-rose-700 flex items-center gap-1.5"
            >
              <Trash2 size={12} /> Remove this route
            </button>
          </div>
        </div>
      )}
    </DrawerShell>
  );
}

function RouteSummary({ route }: { route: RouteRow }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
      <SummaryTile label="Vehicle" value={route.vehicle?.registration_number ?? "—"} icon={Bus} />
      <SummaryTile label="Driver" value={route.driver?.full_name ?? "—"} icon={UserIcon} />
      <SummaryTile label="Morning" value={route.morning_start_time ?? "—"} icon={Sun} />
      <SummaryTile label="Afternoon" value={route.afternoon_start_time ?? "—"} icon={Moon} />
    </div>
  );
}

function SummaryTile({ label, value, icon: Icon }: { label: string; value: string; icon: typeof Bus }) {
  return (
    <div className="bg-slate-50 border border-slate-100 rounded-lg px-3 py-2.5">
      <div className="flex items-center gap-1.5 text-[9px] font-bold uppercase tracking-widest text-slate-400 mb-1">
        <Icon size={10} /> {label}
      </div>
      <p className="text-sm font-bold text-slate-800 truncate">{value}</p>
    </div>
  );
}

// ── Stops ────────────────────────────────────────────────────────────────────

function StopsSection({ routeId, stops }: { routeId: string; stops: StopRow[] }) {
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ name: "", address: "", morning_pickup_time: "", afternoon_dropoff_time: "" });
  const addStop = useAddStop(routeId);
  const deleteStop = useDeleteStop();

  const submit = async () => {
    await addStop.mutateAsync(form);
    setForm({ name: "", address: "", morning_pickup_time: "", afternoon_dropoff_time: "" });
    setAdding(false);
  };

  return (
    <section>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-bold text-slate-800 flex items-center gap-2">
          <MapPin size={14} /> Stops ({stops.length})
        </h3>
        {!adding && (
          <button onClick={() => setAdding(true)} className="text-xs font-semibold text-brand-600 hover:text-brand-700 flex items-center gap-1">
            <Plus size={12} /> Add stop
          </button>
        )}
      </div>

      {stops.length === 0 && !adding ? (
        <p className="text-xs text-slate-400 italic">No stops yet — add the first stop to start the route.</p>
      ) : (
        <div className="rounded-xl border border-slate-200 overflow-hidden divide-y divide-slate-50 mb-2">
          {stops.map((s) => (
            <div key={s.id} className="flex items-center gap-3 px-4 py-2.5 group">
              <div className="w-6 h-6 rounded-full bg-brand-50 text-brand-700 text-[10px] font-bold flex items-center justify-center shrink-0">
                {s.sequence}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-slate-800 truncate">{s.name}</p>
                {s.address && <p className="text-[10px] text-slate-500 truncate">{s.address}</p>}
              </div>
              <div className="flex items-center gap-3 text-[10px] text-slate-500">
                <span className="flex items-center gap-0.5">
                  <Sun size={10} className="text-amber-500" /> {s.morning_pickup_time ?? "—"}
                </span>
                <span className="flex items-center gap-0.5">
                  <Moon size={10} className="text-indigo-500" /> {s.afternoon_dropoff_time ?? "—"}
                </span>
              </div>
              <button
                onClick={() => {
                  if (confirm(`Remove stop "${s.name}"?`)) deleteStop.mutate(s.id);
                }}
                className="p-1 rounded text-slate-300 hover:text-rose-600 hover:bg-rose-50 opacity-0 group-hover:opacity-100"
                title="Remove stop"
              >
                <Trash2 size={12} />
              </button>
            </div>
          ))}
        </div>
      )}

      {adding && (
        <div className="rounded-xl border border-brand-200 bg-brand-50/30 p-4 space-y-3">
          <div>
            <label className="label">Stop name *</label>
            <input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="e.g. Maitama Park"
              className="input"
            />
          </div>
          <div>
            <label className="label">Address</label>
            <input
              value={form.address}
              onChange={(e) => setForm({ ...form, address: e.target.value })}
              className="input"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Morning pickup</label>
              <input
                type="time"
                value={form.morning_pickup_time}
                onChange={(e) => setForm({ ...form, morning_pickup_time: e.target.value })}
                className="input"
              />
            </div>
            <div>
              <label className="label">Afternoon dropoff</label>
              <input
                type="time"
                value={form.afternoon_dropoff_time}
                onChange={(e) => setForm({ ...form, afternoon_dropoff_time: e.target.value })}
                className="input"
              />
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <button onClick={() => setAdding(false)} className="btn-secondary text-xs py-1.5 px-3">Cancel</button>
            <button onClick={submit} disabled={!form.name.trim() || addStop.isPending} className="btn-primary gap-1.5 text-xs py-1.5 px-3">
              {addStop.isPending && <Loader2 size={11} className="animate-spin" />}
              Add stop
            </button>
          </div>
        </div>
      )}
    </section>
  );
}

// ── Roster ───────────────────────────────────────────────────────────────────

function RosterSection({
  routeId, roster, stops,
}: { routeId: string; roster: RosterRow[]; stops: StopRow[] }) {
  const [search, setSearch] = useState("");
  const [showAssign, setShowAssign] = useState(false);
  const { data: students } = useStudents({ page_size: 50, search: search || undefined });
  const assign = useAssignStudent(routeId);
  const unassign = useUnassignStudent(routeId);

  const assignedIds = new Set(roster.map((r) => r.student_id));
  const matches = ((students?.items ?? []) as Array<{
    id: string; first_name: string; last_name: string; student_id: string;
  }>).filter((s) => !assignedIds.has(s.id));

  const firstStop = stops[0]?.id;
  const lastStop = stops[stops.length - 1]?.id;

  return (
    <section>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-bold text-slate-800 flex items-center gap-2">
          <GraduationCap size={14} /> Roster ({roster.length})
        </h3>
        {!showAssign && (
          <button
            onClick={() => setShowAssign(true)}
            className="text-xs font-semibold text-brand-600 hover:text-brand-700 flex items-center gap-1"
          >
            <Plus size={12} /> Assign student
          </button>
        )}
      </div>

      {showAssign && (
        <div className="rounded-xl border border-brand-200 bg-brand-50/30 p-3 mb-3">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search student by name or ID…"
            className="input text-xs mb-2"
            autoFocus
          />
          {matches.length === 0 ? (
            <p className="text-xs text-slate-400 italic px-1">
              {search ? "No students match." : "Type to search."}
            </p>
          ) : (
            <div className="rounded-lg border border-slate-200 max-h-44 overflow-y-auto divide-y divide-slate-50 bg-white">
              {matches.slice(0, 8).map((s) => (
                <button
                  key={s.id}
                  onClick={async () => {
                    await assign.mutateAsync({
                      student_id: s.id,
                      pickup_stop_id: firstStop,
                      dropoff_stop_id: lastStop,
                    });
                    setSearch("");
                  }}
                  className="w-full flex items-center justify-between px-3 py-2 text-left hover:bg-slate-50"
                >
                  <span className="text-xs text-slate-700">
                    <span className="font-semibold">{s.first_name} {s.last_name}</span>
                    <span className="text-slate-400 ml-2">· {s.student_id}</span>
                  </span>
                  <span className="text-[10px] font-bold text-brand-600">Add →</span>
                </button>
              ))}
            </div>
          )}
          <div className="flex justify-end mt-2">
            <button
              onClick={() => { setShowAssign(false); setSearch(""); }}
              className="text-xs text-slate-500 hover:text-slate-700"
            >
              Done
            </button>
          </div>
        </div>
      )}

      {roster.length === 0 ? (
        <p className="text-xs text-slate-400 italic">No students assigned yet.</p>
      ) : (
        <div className="rounded-xl border border-slate-200 overflow-hidden divide-y divide-slate-50">
          {roster.map((r) => (
            <div key={r.assignment_id} className="flex items-center gap-3 px-4 py-2.5 group">
              <div className="w-7 h-7 rounded-full bg-indigo-50 text-indigo-700 text-[10px] font-bold flex items-center justify-center shrink-0">
                {r.first_name[0]}{r.last_name[0]}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-slate-800 truncate">{r.first_name} {r.last_name}</p>
                <p className="text-[10px] text-slate-500 truncate">{r.student_code}</p>
              </div>
              <button
                onClick={() => {
                  if (confirm(`Remove ${r.first_name} ${r.last_name} from this route?`)) {
                    unassign.mutate(r.student_id);
                  }
                }}
                className="p-1 rounded text-slate-300 hover:text-rose-600 hover:bg-rose-50 opacity-0 group-hover:opacity-100"
                title="Remove from roster"
              >
                <Trash2 size={12} />
              </button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

// ── Empty state ──────────────────────────────────────────────────────────────

function EmptyState({ onCreate }: { onCreate: () => void }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-12 text-center">
      <MapPin size={28} className="text-slate-300 mx-auto mb-3" />
      <p className="text-sm font-semibold text-slate-700">No routes yet</p>
      <p className="text-xs text-slate-500 mt-1 mb-4">
        Create your first route to start scheduling school runs.
      </p>
      <button onClick={onCreate} className="btn-primary gap-2 mx-auto">
        <Plus size={14} /> Create first route
      </button>
    </div>
  );
}

// ── Drawer shell ─────────────────────────────────────────────────────────────

function DrawerShell({
  title, onClose, children, wide = false,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  wide?: boolean;
}) {
  return (
    <div className="fixed inset-0 z-50 flex">
      <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm animate-fade-in" onClick={onClose} />
      <div className={cn(
        "relative ml-auto w-full bg-white shadow-2xl overflow-y-auto animate-slide-in flex flex-col",
        wide ? "max-w-2xl" : "max-w-lg",
      )}>
        <div className="sticky top-0 z-10 bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between">
          <h2 className="text-lg font-black text-slate-900 truncate">{title}</h2>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-slate-100 text-slate-500">
            <X size={18} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

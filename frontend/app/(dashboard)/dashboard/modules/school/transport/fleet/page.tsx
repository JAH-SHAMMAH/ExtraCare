"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Bus, Truck, User as UserIcon, Plus, X, Loader2, Trash2, Phone,
  Wrench, ShieldCheck, AlertTriangle,
} from "lucide-react";
import {
  useVehicles, useDrivers,
  useCreateVehicle, useDeleteVehicle,
  useCreateDriver, useDeleteDriver,
  type VehicleRow, type DriverRow, type VehicleStatus,
} from "@/hooks/useTransport";
import { useDelayedFlag } from "@/hooks/useDelayedFlag";
import { Skeleton } from "@/components/loading/Skeleton";
import { cn, formatDate } from "@/lib/utils";

type Tab = "vehicles" | "drivers";

export default function FleetPage() {
  const [tab, setTab] = useState<Tab>("vehicles");
  const [showAdd, setShowAdd] = useState(false);

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
            <Link href="/dashboard/modules/school/transport" className="hover:text-slate-600">Transport</Link>
            <span>/</span>
            <span className="text-brand-600 font-semibold">Fleet</span>
          </nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Fleet</h1>
          <p className="text-slate-500 text-sm mt-0.5">
            School vehicles and the drivers who run them.
          </p>
        </div>
        <button onClick={() => setShowAdd(true)} className="btn-primary gap-2">
          <Plus size={14} /> Add {tab === "vehicles" ? "Vehicle" : "Driver"}
        </button>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-1 inline-flex mb-5">
        {[
          { id: "vehicles" as Tab, label: "Vehicles", icon: Truck },
          { id: "drivers" as Tab, label: "Drivers", icon: UserIcon },
        ].map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={cn(
              "px-4 py-2 text-xs font-bold rounded-lg transition-colors flex items-center gap-2",
              tab === t.id ? "bg-brand-600 text-white" : "text-slate-600 hover:bg-slate-100",
            )}
          >
            <t.icon size={13} />
            {t.label}
          </button>
        ))}
      </div>

      {tab === "vehicles" ? <VehiclesTab /> : <DriversTab />}

      {showAdd && tab === "vehicles" && <AddVehicleDrawer onClose={() => setShowAdd(false)} />}
      {showAdd && tab === "drivers" && <AddDriverDrawer onClose={() => setShowAdd(false)} />}
    </div>
  );
}

// ── Vehicles ─────────────────────────────────────────────────────────────────

function VehiclesTab() {
  const { data, isLoading } = useVehicles();
  const showSkeleton = useDelayedFlag(isLoading);
  const remove = useDeleteVehicle();
  const items = data?.items ?? [];

  if (showSkeleton) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-40 w-full rounded-xl" />
        ))}
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-12 text-center">
        <Truck size={28} className="text-slate-300 mx-auto mb-3" />
        <p className="text-sm font-semibold text-slate-700">No vehicles yet</p>
        <p className="text-xs text-slate-500 mt-1">Add the first bus or van to start running routes.</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {items.map((v) => (
        <VehicleCard
          key={v.id}
          vehicle={v}
          onRemove={() => {
            if (confirm(`Remove ${v.registration_number}?`)) remove.mutate(v.id);
          }}
        />
      ))}
    </div>
  );
}

function VehicleCard({ vehicle, onRemove }: { vehicle: VehicleRow; onRemove: () => void }) {
  const statusMeta: Record<VehicleStatus, { label: string; cls: string }> = {
    active:      { label: "Active",      cls: "bg-emerald-50 text-emerald-700 border-emerald-200" },
    maintenance: { label: "Maintenance", cls: "bg-amber-50 text-amber-700 border-amber-200" },
    retired:     { label: "Retired",     cls: "bg-slate-100 text-slate-500 border-slate-200" },
  };
  const meta = statusMeta[vehicle.status];

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden group">
      <div className="p-5">
        <div className="flex items-start justify-between gap-2 mb-3">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-brand-50 to-indigo-50 text-brand-700 flex items-center justify-center">
            <Bus size={20} />
          </div>
          <div className="flex items-center gap-1.5">
            <span className={cn("badge text-[9px]", meta.cls)}>{meta.label}</span>
            <button
              onClick={onRemove}
              className="p-1.5 rounded text-slate-300 hover:text-rose-600 hover:bg-rose-50 opacity-0 group-hover:opacity-100"
              title="Remove vehicle"
            >
              <Trash2 size={12} />
            </button>
          </div>
        </div>
        <p className="text-base font-black text-slate-900 font-mono">{vehicle.registration_number}</p>
        <p className="text-xs text-slate-500 mt-0.5">
          {[vehicle.make, vehicle.model].filter(Boolean).join(" ") || "—"}
        </p>

        <div className="grid grid-cols-2 gap-2 mt-4 text-xs">
          <Field label="Capacity" value={`${vehicle.capacity} seats`} />
          <Field label="Fuel" value={vehicle.fuel_type ?? "—"} />
          <Field
            label="Last serviced"
            value={vehicle.last_serviced_at ? formatDate(vehicle.last_serviced_at) : "—"}
          />
          <Field label="Color" value={vehicle.color ?? "—"} />
        </div>
      </div>
    </div>
  );
}

// ── Drivers ──────────────────────────────────────────────────────────────────

function DriversTab() {
  const { data, isLoading } = useDrivers();
  const showSkeleton = useDelayedFlag(isLoading);
  const remove = useDeleteDriver();
  const items = data?.items ?? [];

  if (showSkeleton) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-36 w-full rounded-xl" />
        ))}
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-12 text-center">
        <UserIcon size={28} className="text-slate-300 mx-auto mb-3" />
        <p className="text-sm font-semibold text-slate-700">No drivers yet</p>
        <p className="text-xs text-slate-500 mt-1">Add a driver to assign them to a route.</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {items.map((d) => (
        <DriverCard
          key={d.id}
          driver={d}
          onRemove={() => {
            if (confirm(`Remove ${d.full_name}?`)) remove.mutate(d.id);
          }}
        />
      ))}
    </div>
  );
}

function DriverCard({ driver, onRemove }: { driver: DriverRow; onRemove: () => void }) {
  const expiry = driver.license_expiry ? new Date(driver.license_expiry) : null;
  const daysToExpiry = expiry ? Math.ceil((expiry.getTime() - Date.now()) / (1000 * 60 * 60 * 24)) : null;
  const expiringSoon = daysToExpiry !== null && daysToExpiry < 30 && daysToExpiry >= 0;
  const expired = daysToExpiry !== null && daysToExpiry < 0;

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden group">
      <div className="p-5">
        <div className="flex items-start justify-between gap-2 mb-3">
          <div className="w-12 h-12 rounded-xl bg-emerald-50 text-emerald-700 flex items-center justify-center">
            <UserIcon size={18} />
          </div>
          <div className="flex items-center gap-1.5">
            {!driver.is_active && (
              <span className="badge bg-slate-100 text-slate-500 border-slate-200 text-[9px]">Inactive</span>
            )}
            {expired && (
              <span className="badge bg-rose-50 text-rose-700 border-rose-200 text-[9px]">License expired</span>
            )}
            {expiringSoon && !expired && (
              <span className="badge bg-amber-50 text-amber-700 border-amber-200 text-[9px]">License expires soon</span>
            )}
            <button
              onClick={onRemove}
              className="p-1.5 rounded text-slate-300 hover:text-rose-600 hover:bg-rose-50 opacity-0 group-hover:opacity-100"
              title="Remove driver"
            >
              <Trash2 size={12} />
            </button>
          </div>
        </div>
        <p className="text-base font-black text-slate-900">{driver.full_name}</p>
        <p className="text-xs text-slate-500 font-mono mt-0.5 flex items-center gap-1">
          <Phone size={11} /> {driver.phone}
        </p>

        <div className="grid grid-cols-2 gap-2 mt-4 text-xs">
          <Field label="License" value={driver.license_number ?? "—"} mono />
          <Field
            label="Expires"
            value={expiry ? formatDate(driver.license_expiry!) : "—"}
            danger={expired}
            warning={expiringSoon && !expired}
          />
        </div>
      </div>
    </div>
  );
}

// ── Field ────────────────────────────────────────────────────────────────────

function Field({
  label, value, mono = false, danger = false, warning = false,
}: { label: string; value: string; mono?: boolean; danger?: boolean; warning?: boolean }) {
  return (
    <div>
      <p className="text-[9px] font-bold uppercase tracking-widest text-slate-400">{label}</p>
      <p className={cn(
        "text-xs font-semibold mt-0.5 truncate",
        mono && "font-mono",
        danger ? "text-rose-700" : warning ? "text-amber-700" : "text-slate-700",
      )}>
        {value}
      </p>
    </div>
  );
}

// ── Add vehicle drawer ───────────────────────────────────────────────────────

function AddVehicleDrawer({ onClose }: { onClose: () => void }) {
  const create = useCreateVehicle();
  const [form, setForm] = useState({
    registration_number: "", make: "", model: "", color: "",
    capacity: 18, fuel_type: "diesel", status: "active" as VehicleStatus,
  });

  const submit = async () => {
    await create.mutateAsync({ ...form });
    onClose();
  };

  return (
    <DrawerShell title="Add vehicle" onClose={onClose}>
      <div className="p-6 space-y-4">
        <div>
          <label className="label">Registration number *</label>
          <input
            value={form.registration_number}
            onChange={(e) => setForm({ ...form, registration_number: e.target.value })}
            placeholder="e.g. FV-BUS-03"
            className="input font-mono"
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label">Make</label>
            <input value={form.make} onChange={(e) => setForm({ ...form, make: e.target.value })} className="input" />
          </div>
          <div>
            <label className="label">Model</label>
            <input value={form.model} onChange={(e) => setForm({ ...form, model: e.target.value })} className="input" />
          </div>
          <div>
            <label className="label">Color</label>
            <input value={form.color} onChange={(e) => setForm({ ...form, color: e.target.value })} className="input" />
          </div>
          <div>
            <label className="label">Capacity</label>
            <input
              type="number"
              min={1}
              value={form.capacity}
              onChange={(e) => setForm({ ...form, capacity: Number(e.target.value) })}
              className="input"
            />
          </div>
          <div>
            <label className="label">Fuel</label>
            <select
              value={form.fuel_type}
              onChange={(e) => setForm({ ...form, fuel_type: e.target.value })}
              className="input"
            >
              <option value="diesel">Diesel</option>
              <option value="petrol">Petrol</option>
              <option value="electric">Electric</option>
              <option value="hybrid">Hybrid</option>
            </select>
          </div>
          <div>
            <label className="label">Status</label>
            <select
              value={form.status}
              onChange={(e) => setForm({ ...form, status: e.target.value as VehicleStatus })}
              className="input"
            >
              <option value="active">Active</option>
              <option value="maintenance">Maintenance</option>
              <option value="retired">Retired</option>
            </select>
          </div>
        </div>
      </div>
      <div className="sticky bottom-0 bg-white border-t border-slate-200 px-6 py-4 flex items-center justify-end gap-2">
        <button onClick={onClose} className="btn-secondary">Cancel</button>
        <button
          onClick={submit}
          disabled={!form.registration_number.trim() || create.isPending}
          className="btn-primary gap-2"
        >
          {create.isPending && <Loader2 size={14} className="animate-spin" />}
          Add vehicle
        </button>
      </div>
    </DrawerShell>
  );
}

// ── Add driver drawer ────────────────────────────────────────────────────────

function AddDriverDrawer({ onClose }: { onClose: () => void }) {
  const create = useCreateDriver();
  const [form, setForm] = useState({
    full_name: "", phone: "+234", license_number: "", license_expiry: "",
  });

  const submit = async () => {
    await create.mutateAsync({
      ...form,
      license_expiry: form.license_expiry || undefined,
    });
    onClose();
  };

  return (
    <DrawerShell title="Add driver" onClose={onClose}>
      <div className="p-6 space-y-4">
        <div>
          <label className="label">Full name *</label>
          <input
            value={form.full_name}
            onChange={(e) => setForm({ ...form, full_name: e.target.value })}
            className="input"
          />
        </div>
        <div>
          <label className="label">Phone *</label>
          <input
            value={form.phone}
            onChange={(e) => setForm({ ...form, phone: e.target.value })}
            placeholder="+234..."
            className="input font-mono"
          />
          <p className="text-[10px] text-slate-400 mt-1">
            We&apos;ll normalise to E.164 (+234…) automatically.
          </p>
        </div>
        <div>
          <label className="label">License number</label>
          <input
            value={form.license_number}
            onChange={(e) => setForm({ ...form, license_number: e.target.value })}
            className="input font-mono"
          />
        </div>
        <div>
          <label className="label">License expiry</label>
          <input
            type="date"
            value={form.license_expiry}
            onChange={(e) => setForm({ ...form, license_expiry: e.target.value })}
            className="input"
          />
        </div>
      </div>
      <div className="sticky bottom-0 bg-white border-t border-slate-200 px-6 py-4 flex items-center justify-end gap-2">
        <button onClick={onClose} className="btn-secondary">Cancel</button>
        <button
          onClick={submit}
          disabled={!form.full_name.trim() || !form.phone.trim() || create.isPending}
          className="btn-primary gap-2"
        >
          {create.isPending && <Loader2 size={14} className="animate-spin" />}
          Add driver
        </button>
      </div>
    </DrawerShell>
  );
}

function DrawerShell({
  title, onClose, children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="fixed inset-0 z-50 flex">
      <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm animate-fade-in" onClick={onClose} />
      <div className="relative ml-auto w-full max-w-md bg-white shadow-2xl overflow-y-auto animate-slide-in flex flex-col">
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

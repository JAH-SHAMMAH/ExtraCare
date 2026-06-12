"use client";

import { useAuthStore } from "@/lib/store";
import { useLogout } from "@/hooks/useAuth";
import { Settings, Building2, User, Shield, Bell, LogOut } from "lucide-react";

export default function SettingsPage() {
  const { user, org } = useAuthStore();
  const logout = useLogout();

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="mb-8">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
          <span>Core</span><span>/</span>
          <span className="text-brand-600 font-semibold">Settings</span>
        </nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Settings</h1>
        <p className="text-slate-500 text-sm mt-0.5">Manage your account and organization settings.</p>
      </div>

      <div className="space-y-6">
        {/* Profile */}
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h2 className="text-sm font-bold text-slate-800 mb-4 flex items-center gap-2">
            <User size={15} /> Profile
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="label">Full Name</label>
              <input value={user?.full_name || ""} readOnly className="input bg-slate-50" />
            </div>
            <div>
              <label className="label">Email</label>
              <input value={user?.email || ""} readOnly className="input bg-slate-50" />
            </div>
            <div>
              <label className="label">Role</label>
              <input value={user?.primary_role?.replace("_", " ") || ""} readOnly className="input bg-slate-50 capitalize" />
            </div>
            <div>
              <label className="label">Status</label>
              <input value={user?.status || ""} readOnly className="input bg-slate-50 capitalize" />
            </div>
          </div>
        </div>

        {/* Organization */}
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h2 className="text-sm font-bold text-slate-800 mb-4 flex items-center gap-2">
            <Building2 size={15} /> Organization
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="label">Name</label>
              <input value={org?.name || ""} readOnly className="input bg-slate-50" />
            </div>
            <div>
              <label className="label">Slug</label>
              <input value={org?.slug || ""} readOnly className="input bg-slate-50" />
            </div>
            <div>
              <label className="label">Industry</label>
              <input value={org?.industry || ""} readOnly className="input bg-slate-50 capitalize" />
            </div>
          </div>
          {org?.modules_enabled && (
            <div className="mt-4">
              <label className="label">Enabled Modules</label>
              <div className="flex flex-wrap gap-2 mt-1">
                {org.modules_enabled.map((m) => (
                  <span key={m} className="badge bg-brand-50 text-brand-700 border-brand-200">{m}</span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Security */}
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h2 className="text-sm font-bold text-slate-800 mb-4 flex items-center gap-2">
            <Shield size={15} /> Security
          </h2>
          <div className="space-y-3">
            <div className="flex items-center justify-between py-2 border-b border-slate-50">
              <div>
                <p className="text-sm font-medium text-slate-800">Two-Factor Authentication</p>
                <p className="text-xs text-slate-400">Add an extra layer of security to your account.</p>
              </div>
              <span className={`badge ${user?.mfa_enabled ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-50 text-slate-600 border-slate-200"}`}>
                {user?.mfa_enabled ? "Enabled" : "Disabled"}
              </span>
            </div>
            <div className="flex items-center justify-between py-2">
              <div>
                <p className="text-sm font-medium text-slate-800">Permissions</p>
                <p className="text-xs text-slate-400">{user?.permissions?.length || 0} permissions assigned.</p>
              </div>
              <div className="flex flex-wrap gap-1 max-w-xs justify-end">
                {user?.permissions?.slice(0, 4).map((p) => (
                  <span key={p} className="badge bg-slate-50 text-slate-600 border-slate-200 text-[10px]">{p}</span>
                ))}
                {(user?.permissions?.length || 0) > 4 && (
                  <span className="badge bg-slate-50 text-slate-600 border-slate-200 text-[10px]">+{(user?.permissions?.length || 0) - 4} more</span>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Danger zone */}
        <div className="bg-white rounded-xl border border-red-200 p-6">
          <h2 className="text-sm font-bold text-red-700 mb-2">Danger Zone</h2>
          <p className="text-xs text-slate-500 mb-4">Irreversible actions. Please be careful.</p>
          <button onClick={logout} className="px-4 py-2 rounded-lg text-sm font-medium text-red-600 border border-red-200 hover:bg-red-50 transition-colors flex items-center gap-2">
            <LogOut size={14} />
            Sign Out
          </button>
        </div>
      </div>
    </div>
  );
}

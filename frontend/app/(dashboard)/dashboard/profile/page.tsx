"use client";

import { UserRound } from "lucide-react";
import { useState, useRef } from "react";
import { useAuthStore } from "@/lib/store";
import { useLogout } from "@/hooks/useAuth";
import { useUploadAvatar } from "@/hooks/useUpload";
import { usersApi } from "@/lib/api";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  User, Camera, Mail, Phone, Shield, Building2, Loader2,
  Key, Bell, Globe, Save,
} from "lucide-react";
import { cn, getInitials, resolveMediaUrl } from "@/lib/utils";
import { ProfileRoles } from "@/components/role/ProfileRoles";

export default function ProfilePage() {
  const { user, org, setUser } = useAuthStore();
  const logout = useLogout();
  const uploadAvatar = useUploadAvatar();
  const qc = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [editMode, setEditMode] = useState(false);
  const [form, setForm] = useState({
    full_name: user?.full_name || "",
    phone: user?.phone || "",
    department: user?.department || "",
    job_title: user?.job_title || "",
  });

  const updateMutation = useMutation({
    mutationFn: (data: object) => usersApi.update(user!.id, data),
    onSuccess: (data) => {
      // The PATCH response has no permissions/primary_role — merge into the
      // existing session user instead of replacing it (replacing crashed the UI).
      const nameChanged = !!data?.full_name && data.full_name !== user?.full_name;
      if (user) {
        setUser({
          ...user,
          full_name: data.full_name ?? user.full_name,
          phone: data.phone ?? user.phone,
          department: data.department ?? user.department,
          job_title: data.job_title ?? user.job_title,
          avatar_url: data.avatar_url ?? user.avatar_url,
        });
      }
      setEditMode(false);
      qc.invalidateQueries({ queryKey: ["me"] });
      toast.success(nameChanged ? "Name changed successfully." : "Profile updated.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update profile."),
  });

  const handleAvatarChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 25 * 1024 * 1024) {
      toast.error("Image must be under 25MB.");
      return;
    }
    uploadAvatar.mutate(file, {
      onSuccess: (res: { url?: string }) => {
        if (res?.url && user) setUser({ ...user, avatar_url: res.url });
      },
    });
    e.target.value = "";
  };

  return (
    <div className="p-4 sm:p-8 max-w-4xl mx-auto">
      <div className="mb-8">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
          <span>Account</span><span>/</span>
          <span className="text-brand-600 font-semibold">Profile</span>
        </nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">My Profile</h1>
        <p className="text-slate-500 text-sm mt-0.5">Manage your personal information and preferences.</p>
      </div>

      <div className="space-y-6">
        {/* Avatar & Basic Info */}
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <div className="flex flex-col sm:flex-row sm:items-start gap-4 sm:gap-6">
            {/* Avatar */}
            <div className="relative group">
              <div className="w-24 h-24 rounded-2xl bg-brand-600 flex items-center justify-center text-white text-2xl font-bold overflow-hidden border-4 border-white shadow-lg">
                {user?.avatar_url ? (
                  <img src={resolveMediaUrl(user.avatar_url)} alt="" className="w-full h-full object-cover" />
                ) : (
                  <span className="flex flex-col items-center text-white/90">
                    <UserRound size={40} strokeWidth={1.5} aria-hidden />
                    <span className="text-[10px] font-semibold uppercase tracking-wide">No photo yet</span>
                  </span>
                )}
              </div>
              <button
                onClick={() => fileInputRef.current?.click()}
                className="absolute inset-0 rounded-2xl bg-black/40 flex items-center justify-center opacity-0 group-hover:opacity-100 [@media(hover:none)]:opacity-100 transition-opacity cursor-pointer"
              >
                {uploadAvatar.isPending ? (
                  <Loader2 size={20} className="text-white animate-spin" />
                ) : (
                  <Camera size={20} className="text-white" />
                )}
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                onChange={handleAvatarChange}
                className="hidden"
              />
            </div>

            {/* Info */}
            <div className="flex-1 min-w-0">
              <h2 className="text-lg font-bold text-slate-900">{user?.full_name}</h2>
              <p className="text-sm text-slate-500 mt-0.5 break-all">{user?.email}</p>
              {(user?.job_title || user?.department || user?.phone) && (
                <p className="text-sm text-slate-500 mt-1">
                  {[user?.job_title, user?.department, user?.phone].filter(Boolean).join(" · ")}
                </p>
              )}
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploadAvatar.isPending}
                className="btn-secondary gap-2 mt-3 text-xs"
              >
                {uploadAvatar.isPending ? <Loader2 size={14} className="animate-spin" /> : <Camera size={14} />}
                {user?.avatar_url ? "Change photo" : "Upload photo"}
              </button>
              <div className="flex flex-wrap items-center gap-2 mt-3">
                <span className="badge bg-brand-50 text-brand-700 border-brand-200 capitalize">
                  {user?.primary_role?.replace("_", " ")}
                </span>
                <span className={cn(
                  "badge",
                  user?.status === "active" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-50 text-slate-600 border-slate-200"
                )}>
                  {user?.status}
                </span>
              </div>
            </div>

            <button
              onClick={() => {
                if (!editMode) setForm({ full_name: user?.full_name || "", phone: user?.phone || "", department: user?.department || "", job_title: user?.job_title || "" });
                setEditMode(!editMode);
              }}
              className={(editMode ? "btn-secondary" : "btn-primary") + " shrink-0 self-start whitespace-nowrap"}
            >
              {editMode ? "Cancel" : "Edit Profile"}
            </button>
          </div>

          {/* Edit form */}
          {editMode && (
            <div className="mt-6 pt-6 border-t border-slate-100">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="label">Full Name</label>
                  <input
                    value={form.full_name}
                    onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                    className="input"
                  />
                </div>
                <div>
                  <label className="label">Phone</label>
                  <input
                    value={form.phone}
                    onChange={(e) => setForm({ ...form, phone: e.target.value })}
                    placeholder="+234..."
                    className="input"
                  />
                </div>
                <div>
                  <label className="label">Department</label>
                  <input
                    value={form.department}
                    onChange={(e) => setForm({ ...form, department: e.target.value })}
                    className="input"
                  />
                </div>
                <div>
                  <label className="label">Job Title</label>
                  <input
                    value={form.job_title}
                    onChange={(e) => setForm({ ...form, job_title: e.target.value })}
                    className="input"
                  />
                </div>
              </div>
              <div className="flex justify-end mt-4">
                <button
                  onClick={() => {
                  // Send only what changed so untouched (possibly unloaded) fields are never blanked.
                  const changed: Record<string, string> = {};
                  (Object.keys(form) as (keyof typeof form)[]).forEach((k) => {
                    if (form[k] !== ((user?.[k] as string | null | undefined) || "")) changed[k] = form[k];
                  });
                  if (Object.keys(changed).length === 0) { setEditMode(false); return; }
                  updateMutation.mutate(changed);
                }}
                  disabled={updateMutation.isPending}
                  className="btn-primary gap-2"
                >
                  {updateMutation.isPending ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />}
                  Save Changes
                </button>
              </div>
            </div>
          )}
        </div>

        <ProfileRoles />

        {/* Account Details */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <h3 className="text-sm font-bold text-slate-800 mb-4 flex items-center gap-2">
              <Mail size={15} /> Account Information
            </h3>
            <div className="space-y-3">
              <div className="flex justify-between py-2 border-b border-slate-50">
                <span className="text-sm text-slate-500">Email</span>
                <span className="text-sm font-medium text-slate-800">{user?.email}</span>
              </div>
              <div className="flex justify-between py-2 border-b border-slate-50">
                <span className="text-sm text-slate-500">Email Verified</span>
                <span className={cn("badge text-xs", user?.mfa_enabled ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-orange-50 text-orange-700 border-orange-200")}>
                  {user?.mfa_enabled ? "Verified" : "Pending"}
                </span>
              </div>
              <div className="flex justify-between py-2">
                <span className="text-sm text-slate-500">User ID</span>
                <span className="text-xs font-mono text-slate-400">{user?.id?.slice(0, 12)}...</span>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <h3 className="text-sm font-bold text-slate-800 mb-4 flex items-center gap-2">
              <Building2 size={15} /> Organization
            </h3>
            <div className="space-y-3">
              <div className="flex justify-between py-2 border-b border-slate-50">
                <span className="text-sm text-slate-500">Organization</span>
                <span className="text-sm font-medium text-slate-800">{org?.name}</span>
              </div>
              <div className="flex justify-between py-2">
                <span className="text-sm text-slate-500">Industry</span>
                <span className="text-sm font-medium text-slate-800 capitalize">{org?.industry}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Security */}
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h3 className="text-sm font-bold text-slate-800 mb-4 flex items-center gap-2">
            <Shield size={15} /> Security & Permissions
          </h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between py-2 border-b border-slate-50">
              <div>
                <p className="text-sm font-medium text-slate-800">Two-Factor Authentication</p>
                <p className="text-xs text-slate-400">Add an extra layer of security.</p>
              </div>
              <span className={cn("badge", user?.mfa_enabled ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-50 text-slate-600 border-slate-200")}>
                {user?.mfa_enabled ? "Enabled" : "Disabled"}
              </span>
            </div>
            <div className="flex items-center justify-between py-2 border-b border-slate-50">
              <div>
                <p className="text-sm font-medium text-slate-800">Role</p>
                <p className="text-xs text-slate-400">Your primary access level.</p>
              </div>
              <span className="badge bg-brand-50 text-brand-700 border-brand-200 capitalize">
                {user?.primary_role?.replace("_", " ")}
              </span>
            </div>
            <div>
              <p className="text-sm font-medium text-slate-800 mb-2">Permissions ({user?.permissions?.length || 0})</p>
              <div className="flex flex-wrap gap-1.5">
                {user?.permissions?.map((p) => (
                  <span key={p} className="badge bg-slate-50 text-slate-600 border-slate-200 text-[10px]">{p}</span>
                ))}
                {(!user?.permissions || user.permissions.length === 0) && (
                  <span className="text-xs text-slate-400">No explicit permissions assigned.</span>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

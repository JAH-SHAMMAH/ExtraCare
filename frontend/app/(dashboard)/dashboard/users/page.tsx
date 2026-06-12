"use client";

import { useState } from "react";
import { useUsers, useUpdateUserStatus, useDeleteUser, useAvailableRoles } from "@/hooks/useUsers";
import { UserCreateModal } from "@/components/users/UserCreateModal";
import { cn, timeAgo, STATUS_COLORS, getInitials } from "@/lib/utils";
import { Search, Download, UserPlus, MoreVertical, Shield, Ban, Trash2, Edit } from "lucide-react";
import type { User, UserStatus } from "@/types";
import { useAuthStore } from "@/lib/store";

export default function UsersPage() {
  const { hasPermission } = useAuthStore();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<UserStatus | undefined>();
  const [page, setPage] = useState(1);
  const [createModalOpen, setCreateModalOpen] = useState(false);

  const { data, isLoading } = useUsers({ page, page_size: 25, search: search || undefined, status: statusFilter });
  const { data: rolesData } = useAvailableRoles();
  const { mutate: updateStatus } = useUpdateUserStatus();
  const { mutate: deleteUser } = useDeleteUser();

  const canWrite = hasPermission("users:write");
  const canDelete = hasPermission("users:delete");

  return (
    <div className="p-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
            <span>HR</span>
            <span>/</span>
            <span className="text-brand-600 font-semibold">User Directory</span>
          </nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">User Directory</h1>
          <p className="text-slate-500 text-sm mt-0.5">Manage access and security roles across your organization.</p>
        </div>
        {canWrite && (
          <div className="flex items-center gap-3">
            <button className="btn-secondary gap-2">
              <Download size={15} />
              Export
            </button>
            <button className="btn-primary gap-2" onClick={() => setCreateModalOpen(true)}>
              <UserPlus size={15} />
              Add User
            </button>
          </div>
        )}
      </div>

      {/* Stats strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {[
          { label: "Total Users", value: data?.total ?? "—" },
          { label: "Active", value: "—" },
          { label: "Pending", value: "—" },
          { label: "Suspended", value: "—" },
        ].map(({ label, value }) => (
          <div key={label} className="bg-white rounded-xl border border-slate-200 p-4">
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">{label}</p>
            <p className="text-xl font-black text-slate-900">{value}</p>
          </div>
        ))}
      </div>

      {/* Filter bar */}
      <div className="bg-white rounded-xl border border-slate-200 p-3 mb-4 flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-64">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            placeholder="Search by name, email, department..."
            className="input pl-9"
          />
        </div>
        <select
          value={statusFilter || ""}
          onChange={(e) => { setStatusFilter(e.target.value as UserStatus || undefined); setPage(1); }}
          className="input w-auto px-3 py-2 text-sm"
        >
          <option value="">All Statuses</option>
          <option value="active">Active</option>
          <option value="suspended">Suspended</option>
          <option value="pending">Pending</option>
          <option value="inactive">Inactive</option>
        </select>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="bg-slate-50/80 border-b border-slate-100">
                {["User", "Role", "Status", "Last Login", ""].map((h) => (
                  <th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500 whitespace-nowrap">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {isLoading
                ? Array.from({ length: 8 }).map((_, i) => <SkeletonRow key={i} />)
                : data?.items?.map((user) => (
                  <UserRow
                    key={user.id}
                    user={user}
                    canWrite={canWrite}
                    canDelete={canDelete}
                    onSuspend={() => updateStatus({ id: user.id, status: "suspended" })}
                    onActivate={() => updateStatus({ id: user.id, status: "active" })}
                    onDelete={() => deleteUser(user.id)}
                  />
                ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {data && data.total_pages > 1 && (
          <div className="px-5 py-4 border-t border-slate-100 flex items-center justify-between">
            <p className="text-xs text-slate-500">
              Showing {(page - 1) * 25 + 1}–{Math.min(page * 25, data.total)} of {data.total} users
            </p>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-3 py-1.5 text-xs font-medium rounded-lg text-slate-600 hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Prev
              </button>
              {Array.from({ length: Math.min(data.total_pages, 5) }, (_, i) => i + 1).map((p) => (
                <button
                  key={p}
                  onClick={() => setPage(p)}
                  className={cn(
                    "px-3 py-1.5 text-xs font-bold rounded-lg",
                    page === p ? "bg-brand-600 text-white" : "text-slate-600 hover:bg-slate-100"
                  )}
                >
                  {p}
                </button>
              ))}
              <button
                onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
                disabled={page === data.total_pages}
                className="px-3 py-1.5 text-xs font-medium rounded-lg text-slate-600 hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Create User Modal */}
      <UserCreateModal
        open={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
        availableRoles={rolesData?.items || []}
        onSuccess={() => setPage(1)}
      />
    </div>
  );
}

function UserRow({ user, canWrite, canDelete, onSuspend, onActivate, onDelete }: {
  user: User;
  canWrite: boolean;
  canDelete: boolean;
  onSuspend: () => void;
  onActivate: () => void;
  onDelete: () => void;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const primaryRole = user.roles?.[0];

  return (
    <tr className="group hover:bg-slate-50/70 transition-colors">
      <td className="px-5 py-4">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-brand-600/10 border border-brand-100 flex items-center justify-center text-brand-700 text-sm font-bold shrink-0">
            {getInitials(user.full_name)}
          </div>
          <div>
            <p className="text-sm font-bold text-slate-900">{user.full_name}</p>
            <p className="text-xs text-slate-400">{user.email}</p>
          </div>
        </div>
      </td>
      <td className="px-5 py-4">
        {primaryRole && (
          <span className="badge bg-blue-50 text-blue-700 border-blue-200">
            {primaryRole.name}
          </span>
        )}
      </td>
      <td className="px-5 py-4">
        <span className={cn("badge", STATUS_COLORS[user.status] || "bg-slate-50 text-slate-600 border-slate-200")}>
          <span className={cn(
            "w-1.5 h-1.5 rounded-full mr-1.5",
            user.status === "active" ? "bg-emerald-500" :
            user.status === "suspended" ? "bg-orange-500" :
            user.status === "pending" ? "bg-blue-500" : "bg-slate-400"
          )} />
          {user.status}
        </span>
      </td>
      <td className="px-5 py-4">
        <p className="text-xs text-slate-600">{timeAgo(user.last_login_at)}</p>
        {user.last_login_ip && <p className="text-[10px] text-slate-400">IP: {user.last_login_ip}</p>}
      </td>
      <td className="px-5 py-4 text-right">
        {canWrite && (
          <div className="relative inline-block">
            <button
              onClick={() => setMenuOpen((o) => !o)}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors opacity-0 group-hover:opacity-100"
            >
              <MoreVertical size={15} />
            </button>
            {menuOpen && (
              <div className="absolute right-0 top-full mt-1 w-44 bg-white rounded-xl border border-slate-200 shadow-lg z-50 py-1">
                <MenuItem icon={Edit} label="Edit user" onClick={() => setMenuOpen(false)} />
                <MenuItem icon={Shield} label="Change role" onClick={() => setMenuOpen(false)} />
                {user.status === "active"
                  ? <MenuItem icon={Ban} label="Suspend" onClick={() => { onSuspend(); setMenuOpen(false); }} className="text-orange-600" />
                  : <MenuItem icon={Shield} label="Activate" onClick={() => { onActivate(); setMenuOpen(false); }} className="text-emerald-600" />
                }
                {canDelete && (
                  <MenuItem icon={Trash2} label="Remove user" onClick={() => { onDelete(); setMenuOpen(false); }} className="text-red-600" />
                )}
              </div>
            )}
          </div>
        )}
      </td>
    </tr>
  );
}

function MenuItem({ icon: Icon, label, onClick, className }: { icon: any; label: string; onClick: () => void; className?: string }) {
  return (
    <button
      onClick={onClick}
      className={cn("flex items-center gap-2.5 w-full px-3.5 py-2 text-sm text-slate-600 hover:bg-slate-50 transition-colors", className)}
    >
      <Icon size={14} />
      {label}
    </button>
  );
}

function SkeletonRow() {
  return (
    <tr className="border-b border-slate-50">
      {Array.from({ length: 5 }).map((_, i) => (
        <td key={i} className="px-5 py-4">
          <div className="h-4 bg-slate-100 rounded animate-pulse w-24" />
        </td>
      ))}
    </tr>
  );
}

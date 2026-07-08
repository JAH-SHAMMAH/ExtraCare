"use client";

import { useState } from "react";
import {
  useClubs,
  useCreateClub,
  useUpdateClub,
  useDeleteClub,
  useClubMembers,
  useJoinClub,
  useLeaveClub,
} from "@/hooks/useSchoolExperience";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn, formatDate } from "@/lib/utils";
import {
  Users2, Plus, X, Loader2, Edit2, Trash2, MoreVertical, ArrowLeft,
  Clock, MapPin, Calendar, UserPlus, UserMinus,
} from "lucide-react";
import type { Club, ClubMembership } from "@/types";

export default function ClubsPage() {
  const canWrite = useHasPermission("school:write");
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<Club | null>(null);
  const [menuOpen, setMenuOpen] = useState<string | null>(null);
  const [openClub, setOpenClub] = useState<Club | null>(null);

  const { data, isLoading } = useClubs({ page: 1, page_size: 50 });
  const createClub = useCreateClub();
  const updateClub = useUpdateClub();
  const deleteClub = useDeleteClub();

  const [form, setForm] = useState({
    name: "",
    description: "",
    advisor_id: "",
    meeting_day: "",
    meeting_time: "",
    location: "",
    max_members: "",
    cover_url: "",
    is_active: true,
  });

  const resetForm = () => {
    setForm({
      name: "", description: "", advisor_id: "", meeting_day: "",
      meeting_time: "", location: "", max_members: "", cover_url: "", is_active: true,
    });
    setEditing(null);
    setShowForm(false);
  };

  const handleSubmit = () => {
    const payload = {
      name: form.name,
      description: form.description || null,
      advisor_id: form.advisor_id || null,
      meeting_day: form.meeting_day || null,
      meeting_time: form.meeting_time || null,
      location: form.location || null,
      cover_url: form.cover_url || null,
      max_members: form.max_members ? Number(form.max_members) : null,
      is_active: form.is_active,
    };
    if (editing) {
      updateClub.mutate({ id: editing.id, data: payload }, { onSuccess: resetForm });
    } else {
      createClub.mutate(payload, { onSuccess: resetForm });
    }
  };

  const handleEdit = (c: Club) => {
    setForm({
      name: c.name,
      description: c.description || "",
      advisor_id: c.advisor_id || "",
      meeting_day: c.meeting_day || "",
      meeting_time: c.meeting_time || "",
      location: c.location || "",
      max_members: c.max_members?.toString() || "",
      cover_url: c.cover_url || "",
      is_active: c.is_active,
    });
    setEditing(c);
    setShowForm(true);
    setMenuOpen(null);
  };

  const handleDelete = (id: string) => {
    if (confirm("Delete this club? Memberships will be ended.")) {
      deleteClub.mutate(id);
    }
    setMenuOpen(null);
  };

  if (openClub) {
    return <ClubMembersView club={openClub} onBack={() => setOpenClub(null)} canManage={canWrite} />;
  }

  const clubs = data?.items as Club[] | undefined;

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
            <span>Education</span><span>/</span>
            <span className="text-brand-600 font-semibold">Clubs &amp; Activities</span>
          </nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Clubs &amp; Activities</h1>
          <p className="text-slate-500 text-sm mt-0.5">
            Manage extracurricular clubs, members, and meetings.
          </p>
        </div>
        {canWrite && (
          <button onClick={() => { resetForm(); setShowForm(true); }} className="btn-primary gap-2">
            <Plus size={15} />
            New Club
          </button>
        )}
      </div>

      {showForm && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold text-slate-800">{editing ? "Edit Club" : "New Club"}</h2>
            <button onClick={resetForm} className="text-slate-400 hover:text-slate-600"><X size={16} /></button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="md:col-span-2">
              <label className="label">Club Name *</label>
              <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="input" />
            </div>
            <div>
              <label className="label">Advisor ID</label>
              <input value={form.advisor_id} onChange={(e) => setForm({ ...form, advisor_id: e.target.value })} className="input" />
            </div>
            <div>
              <label className="label">Max Members</label>
              <input type="number" value={form.max_members} onChange={(e) => setForm({ ...form, max_members: e.target.value })} className="input" />
            </div>
            <div>
              <label className="label">Meeting Day</label>
              <select value={form.meeting_day} onChange={(e) => setForm({ ...form, meeting_day: e.target.value })} className="input">
                <option value="">—</option>
                {["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"].map((d) => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">Meeting Time</label>
              <input type="time" value={form.meeting_time} onChange={(e) => setForm({ ...form, meeting_time: e.target.value })} className="input" />
            </div>
            <div>
              <label className="label">Location</label>
              <input value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} className="input" />
            </div>
            <div>
              <label className="label">Cover Image URL</label>
              <input value={form.cover_url} onChange={(e) => setForm({ ...form, cover_url: e.target.value })} className="input" />
            </div>
            <div className="md:col-span-2">
              <label className="label">Description</label>
              <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="input" rows={3} />
            </div>
            <div className="md:col-span-2 flex items-center gap-2">
              <input
                id="active"
                type="checkbox"
                checked={form.is_active}
                onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
              />
              <label htmlFor="active" className="text-xs font-medium text-slate-700">Active</label>
            </div>
          </div>
          <div className="flex justify-end gap-3 mt-4">
            <button onClick={resetForm} className="btn-secondary">Cancel</button>
            <button onClick={handleSubmit} disabled={createClub.isPending || updateClub.isPending} className="btn-primary gap-2">
              {(createClub.isPending || updateClub.isPending) && <Loader2 size={15} className="animate-spin" />}
              {editing ? "Update" : "Create"}
            </button>
          </div>
        </div>
      )}

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-52 bg-slate-100 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : clubs && clubs.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {clubs.map((c) => (
            <div key={c.id} className="bg-white rounded-xl border border-slate-200 overflow-hidden hover:shadow-md transition-shadow">
              {c.cover_url ? (
                <div className="h-28 bg-slate-100 bg-cover bg-center" style={{ backgroundImage: `url(${c.cover_url})` }} />
              ) : (
                <div className="h-28 bg-gradient-to-br from-brand-500 to-indigo-600 flex items-center justify-center">
                  <Users2 size={32} className="text-white/80" />
                </div>
              )}
              <div className="p-5">
                <div className="flex items-start justify-between mb-2">
                  <h3 className="text-sm font-bold text-slate-900 flex-1">{c.name}</h3>
                  {canWrite && (
                    <div className="relative">
                      <button onClick={() => setMenuOpen(menuOpen === c.id ? null : c.id)} className="p-1 rounded hover:bg-slate-100">
                        <MoreVertical size={14} className="text-slate-400" />
                      </button>
                      {menuOpen === c.id && (
                        <div className="absolute right-0 top-full mt-1 w-36 bg-white rounded-lg border border-slate-200 shadow-lg z-10 py-1">
                          <button onClick={() => handleEdit(c)} className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50">
                            <Edit2 size={13} /> Edit
                          </button>
                          <button onClick={() => handleDelete(c.id)} className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-600 hover:bg-red-50">
                            <Trash2 size={13} /> Delete
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                </div>
                {c.description && <p className="text-xs text-slate-500 line-clamp-2 mb-3">{c.description}</p>}
                <div className="space-y-1 mb-3">
                  {c.meeting_day && (
                    <div className="flex items-center gap-1.5 text-xs text-slate-500">
                      <Calendar size={12} /> {c.meeting_day}
                      {c.meeting_time && <span>· <Clock size={10} className="inline" /> {c.meeting_time}</span>}
                    </div>
                  )}
                  {c.location && (
                    <div className="flex items-center gap-1.5 text-xs text-slate-500">
                      <MapPin size={12} /> {c.location}
                    </div>
                  )}
                  <div className="flex items-center gap-1.5 text-xs text-slate-500">
                    <Users2 size={12} />
                    {c.member_count ?? 0} members
                    {c.max_members && <span className="text-slate-400"> / {c.max_members} max</span>}
                  </div>
                </div>
                <button
                  onClick={() => setOpenClub(c)}
                  className="w-full text-xs font-semibold text-brand-600 hover:text-brand-700 border-t border-slate-100 pt-3"
                >
                  Manage Members →
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400">
          <Users2 size={36} className="mb-3 opacity-40" />
          <p className="font-semibold">No clubs yet</p>
        </div>
      )}
    </div>
  );
}

function ClubMembersView({ club, onBack, canManage }: { club: Club; onBack: () => void; canManage: boolean }) {
  const { data, isLoading } = useClubMembers(club.id);
  const joinClub = useJoinClub();
  const leaveClub = useLeaveClub();
  const [showAdd, setShowAdd] = useState(false);
  const [studentId, setStudentId] = useState("");
  const [role, setRole] = useState("member");

  const handleAdd = () => {
    joinClub.mutate(
      { club_id: club.id, student_id: studentId, role },
      { onSuccess: () => { setStudentId(""); setRole("member"); setShowAdd(false); } },
    );
  };

  const members = data as ClubMembership[] | undefined;

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <button onClick={onBack} className="flex items-center gap-2 text-xs text-slate-500 hover:text-slate-700 mb-4">
        <ArrowLeft size={14} /> Back to clubs
      </button>
      <div className="flex items-end justify-between mb-6">
        <div>
          <h1 className="text-2xl font-black text-slate-900">{club.name}</h1>
          <p className="text-sm text-slate-500 mt-1">{members?.length ?? 0} members</p>
        </div>
        {canManage && (
          <button onClick={() => setShowAdd((s) => !s)} className="btn-primary gap-2">
            <UserPlus size={15} /> Add Member
          </button>
        )}
      </div>

      {showAdd && canManage && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 mb-4 grid grid-cols-1 md:grid-cols-3 gap-3 items-end">
          <div>
            <label className="label">Student ID</label>
            <input value={studentId} onChange={(e) => setStudentId(e.target.value)} className="input" />
          </div>
          <div>
            <label className="label">Role</label>
            <select value={role} onChange={(e) => setRole(e.target.value)} className="input">
              <option value="member">Member</option>
              <option value="president">President</option>
              <option value="secretary">Secretary</option>
              <option value="treasurer">Treasurer</option>
            </select>
          </div>
          <button onClick={handleAdd} disabled={!studentId || joinClub.isPending} className="btn-primary gap-2">
            {joinClub.isPending && <Loader2 size={14} className="animate-spin" />}
            Add
          </button>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        <table className="w-full text-left">
          <thead>
            <tr className="bg-slate-50/80 border-b border-slate-100">
              {["Student", "Role", "Joined", "Status", ""].map((h) => (
                <th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? (
              Array.from({ length: 4 }).map((_, i) => (
                <tr key={i}>{Array.from({ length: 5 }).map((_, j) => (
                  <td key={j} className="px-5 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-24" /></td>
                ))}</tr>
              ))
            ) : members && members.length > 0 ? (
              members.map((m) => (
                <tr key={m.id} className="hover:bg-slate-50/70">
                  <td className="px-5 py-4"><span className="text-xs font-mono text-slate-600">{m.student_id.slice(0, 8)}</span></td>
                  <td className="px-5 py-4"><span className="text-sm text-slate-700 capitalize">{m.role}</span></td>
                  <td className="px-5 py-4"><span className="text-xs text-slate-500">{formatDate(m.joined_at)}</span></td>
                  <td className="px-5 py-4">
                    <span className={cn("badge", m.is_active ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-50 text-slate-500 border-slate-200")}>
                      {m.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="px-5 py-4">
                    {canManage && m.is_active && (
                      <button
                        onClick={() => { if (confirm("Remove this member?")) leaveClub.mutate(m.id); }}
                        className="text-slate-400 hover:text-red-600 p-1"
                      >
                        <UserMinus size={13} />
                      </button>
                    )}
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={5} className="py-12 text-center text-slate-400 text-sm">No members yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

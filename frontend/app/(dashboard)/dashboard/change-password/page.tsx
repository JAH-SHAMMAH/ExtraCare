"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useChangePassword } from "@/hooks/useAuth";
import { useAuthStore } from "@/lib/store";
import { KeyRound, Loader2, ShieldAlert } from "lucide-react";

export default function ChangePasswordPage() {
  const router = useRouter();
  const { user } = useAuthStore();
  const change = useChangePassword();
  const forced = !!user?.force_password_change;

  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [err, setErr] = useState("");

  const submit = () => {
    setErr("");
    if (next !== confirm) { setErr("New passwords don't match."); return; }
    change.mutate(
      { current_password: current, new_password: next },
      { onSuccess: () => router.replace("/dashboard") },
    );
  };

  return (
    <div className="p-8 max-w-md mx-auto">
      <div className="mb-6">
        <div className="w-11 h-11 rounded-xl bg-brand-50 text-brand-600 flex items-center justify-center mb-3"><KeyRound size={20} /></div>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Change Password</h1>
        <p className="text-slate-500 text-sm mt-0.5">Set a new password for your account.</p>
      </div>

      {forced && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-5 flex items-start gap-3">
          <ShieldAlert size={18} className="text-amber-600 shrink-0 mt-0.5" />
          <p className="text-sm text-amber-800">An administrator reset your password. Please choose a new one before continuing.</p>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
        <div>
          <label className="label">{forced ? "Temporary password" : "Current password"}</label>
          <input type="password" value={current} onChange={(e) => setCurrent(e.target.value)} className="input" autoFocus />
        </div>
        <div>
          <label className="label">New password</label>
          <input type="password" value={next} onChange={(e) => setNext(e.target.value)} className="input" />
          <p className="text-[11px] text-slate-400 mt-1">At least 8 characters, with an uppercase letter and a number.</p>
        </div>
        <div>
          <label className="label">Confirm new password</label>
          <input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} className="input" />
        </div>
        {err && <p className="text-xs text-red-600">{err}</p>}
        <button
          onClick={submit}
          disabled={change.isPending || !current || !next || !confirm}
          className="btn-primary gap-2 w-full justify-center"
        >
          {change.isPending && <Loader2 size={15} className="animate-spin" />}Change Password
        </button>
      </div>
    </div>
  );
}

"use client";

import Link from "next/link";
import { GraduationCap, ShieldCheck, ArrowRight } from "lucide-react";

/**
 * Self-service registration is disabled for the Fairview School Portal — there
 * is a single school and accounts are provisioned by an administrator. This
 * page exists only so the /register URL (and any old links) resolves to a clear
 * notice instead of the legacy multi-tenant signup flow.
 */
export default function RegisterPage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-brand-600 via-brand-700 to-brand-900 flex items-center justify-center p-4">
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-96 h-96 rounded-full bg-white/5 blur-3xl" />
        <div className="absolute -bottom-40 -left-40 w-96 h-96 rounded-full bg-white/5 blur-3xl" />
      </div>

      <div className="relative w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 bg-white/10 rounded-xl mb-4 border border-white/20">
            <GraduationCap className="w-6 h-6 text-white" />
          </div>
          <h1 className="text-2xl font-black text-white tracking-tight">Fairview School Portal</h1>
        </div>

        <div className="bg-white rounded-2xl shadow-2xl shadow-black/20 p-8 text-center">
          <div className="w-12 h-12 rounded-xl bg-brand-50 flex items-center justify-center mx-auto mb-4">
            <ShieldCheck className="w-6 h-6 text-brand-600" />
          </div>
          <h2 className="text-lg font-black text-slate-900">Accounts are by invitation</h2>
          <p className="text-sm text-slate-500 mt-2 leading-6">
            The Fairview School Portal does not offer public sign-up. Staff, parent,
            and student accounts are created by a school administrator. If you need
            access, please contact the school office.
          </p>

          <Link
            href="/login"
            className="btn-primary w-full mt-6 inline-flex items-center justify-center gap-2"
          >
            Go to sign in <ArrowRight size={16} />
          </Link>
        </div>

        <p className="text-center text-white/40 text-xs mt-6">© 2026 Fairview School Portal</p>
      </div>
    </div>
  );
}

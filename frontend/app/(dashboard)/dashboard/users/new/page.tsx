"use client";

import { useRouter } from "next/navigation";
import { useAvailableRoles } from "@/hooks/useUsers";
import { UserCreateModal } from "@/components/users/UserCreateModal";

export default function CreateStaffPage() {
  const router = useRouter();
  const { data } = useAvailableRoles();
  const roles = Array.isArray(data) ? data : data?.items ?? [];
  return (
    <div className="p-8 max-w-3xl mx-auto">
      <h1 className="text-2xl font-black text-slate-900 tracking-tight">Create Staff / Admin</h1>
      <p className="text-sm text-slate-500 mt-1">Fill in the details and choose a role. Share the sign-in details with the person yourself.</p>
      <UserCreateModal open onClose={() => router.push("/dashboard/users")} availableRoles={roles} onSuccess={() => router.push("/dashboard/users")} />
    </div>
  );
}

"use client";

import { useState, useEffect } from "react";
import { X, Loader2, Eye, EyeOff } from "lucide-react";
import { useCreateUser } from "@/hooks/useUsers";
import { useHrList } from "@/hooks/useHrAdmin";
import { useSections } from "@/hooks/usePlatform";
import { useSubjectOptions } from "@/hooks/useAcademics";
import { isTeachingRoleSlug } from "@/lib/teachingRoles";
import { FormField } from "@/components/ui/FormField";
import type { User } from "@/types";

interface UserCreateModalProps {
  open: boolean;
  onClose: () => void;
  availableRoles?: Array<{ id: string; name: string; slug: string; color: string }>;
  onSuccess?: (user: User) => void;
}

export function UserCreateModal({ open, onClose, availableRoles = [], onSuccess }: UserCreateModalProps) {
  const [formData, setFormData] = useState({
    email: "",
    full_name: "",
    password: "",
    phone: "",
    department: "",
    job_title: "",
    role_ids: [] as string[],
    section_ids: [] as string[],
    subject_ids: [] as string[],
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [showPassword, setShowPassword] = useState(false);

  // Suggest the HR-managed Departments / Job Titles (still free-text, so existing
  // values keep working). Empty + silent if the creator lacks hr:write.
  const { data: departments } = useHrList("hr_department");
  const { data: jobTitles } = useHrList("job_title");
  const activeNames = (items?: { name: string; is_active: boolean }[]) => (items ?? []).filter((i) => i.is_active).map((i) => i.name);

  const { mutate: createUser, isPending } = useCreateUser();

  // A teaching role (Teacher, Head Teacher, …) must belong to a school section:
  // it decides which report menus and pupils that teacher gets.
  const { data: sectionList } = useSections();
  const sections: Array<{ id: string; name: string }> = Array.isArray(sectionList) ? sectionList : [];
  const { data: subjectData } = useSubjectOptions();
  const allSubjects: Array<{ id: string; name: string; section_id?: string | null }> = subjectData?.items ?? [];
  // Offer the subjects of the chosen section(s); drop ones whose section was un-ticked on save.
  const subjectsForSections = allSubjects.filter((x) => formData.section_ids.includes(x.section_id ?? ""));
  const needsSection = availableRoles.some((r) => formData.role_ids.includes(r.id) && isTeachingRoleSlug(r.slug));

  // Reset form when modal opens
  useEffect(() => {
    if (open) {
      setFormData({
        email: "",
        full_name: "",
        password: "",
        phone: "",
        department: "",
        job_title: "",
        role_ids: [],
        section_ids: [],
        subject_ids: [],
      });
      setErrors({});
      setShowPassword(false);
    }
  }, [open]);

  const validateForm = () => {
    const newErrors: Record<string, string> = {};

    if (!formData.email.trim()) {
      newErrors.email = "Email is required";
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      newErrors.email = "Invalid email address";
    }

    if (!formData.full_name.trim()) {
      newErrors.full_name = "Full name is required";
    }

    if (!formData.password.trim()) {
      newErrors.password = "Password is required";
    } else if (formData.password.length < 8) {
      newErrors.password = "Password must be at least 8 characters";
    }

    if (formData.role_ids.length === 0) {
      newErrors.role_ids = "Select at least one role";
    }

    if (needsSection && formData.section_ids.length === 0) {
      newErrors.section_ids = "Choose at least one section for a teacher";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    createUser({
      ...formData,
      section_ids: needsSection ? formData.section_ids : [],
      subject_ids: needsSection ? formData.subject_ids.filter((id) => subjectsForSections.some((x) => x.id === id)) : [],
    }, {
      onSuccess: (user: User) => {
        setFormData({
          email: "",
          full_name: "",
          password: "",
          phone: "",
          department: "",
          job_title: "",
          role_ids: [],
          section_ids: [],
          subject_ids: [],
        });
        setErrors({});
        onClose();
        onSuccess?.(user);
      },
    });
  };

  const handleRoleToggle = (roleId: string) => {
    setFormData((prev) => ({
      ...prev,
      role_ids: prev.role_ids.includes(roleId)
        ? prev.role_ids.filter((id) => id !== roleId)
        : [...prev.role_ids, roleId],
    }));
    if (errors.role_ids) {
      setErrors((prev) => ({ ...prev, role_ids: "" }));
    }
  };

  const handleSectionToggle = (id: string) => {
    setFormData((prev) => ({
      ...prev,
      section_ids: prev.section_ids.includes(id) ? prev.section_ids.filter((x) => x !== id) : [...prev.section_ids, id],
    }));
    if (errors.section_ids) setErrors((prev) => ({ ...prev, section_ids: "" }));
  };

  if (!open) return null;

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/30 z-40" onClick={onClose} />

      {/* Modal */}
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
          {/* Header */}
          <div className="sticky top-0 bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold text-slate-900">Create User</h2>
              <p className="text-sm text-slate-500 mt-0.5">Add a new user to your organization</p>
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
              disabled={isPending}
            >
              <X size={20} className="text-slate-400" />
            </button>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="p-6 space-y-5">
            {/* Email */}
            <FormField
              label="Email Address"
              error={errors.email}
              required
            >
              <input
                type="email"
                value={formData.email}
                onChange={(e) => {
                  setFormData((prev) => ({ ...prev, email: e.target.value }));
                  if (errors.email) setErrors((prev) => ({ ...prev, email: "" }));
                }}
                placeholder="user@example.com"
                className="input"
                disabled={isPending}
              />
            </FormField>

            {/* Full Name */}
            <FormField
              label="Full Name"
              error={errors.full_name}
              required
            >
              <input
                type="text"
                value={formData.full_name}
                onChange={(e) => {
                  setFormData((prev) => ({ ...prev, full_name: e.target.value }));
                  if (errors.full_name) setErrors((prev) => ({ ...prev, full_name: "" }));
                }}
                placeholder="John Doe"
                className="input"
                disabled={isPending}
              />
            </FormField>

            {/* Password */}
            <FormField
              label="Password"
              error={errors.password}
              required
            >
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  value={formData.password}
                  onChange={(e) => {
                    setFormData((prev) => ({ ...prev, password: e.target.value }));
                    if (errors.password) setErrors((prev) => ({ ...prev, password: "" }));
                  }}
                  placeholder="Minimum 8 characters"
                  className="input pr-10"
                  disabled={isPending}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </FormField>

            {/* Phone & Department (Two columns) */}
            <div className="grid grid-cols-2 gap-4">
              <FormField label="Phone" error={errors.phone}>
                <input
                  type="tel"
                  value={formData.phone}
                  onChange={(e) => {
                    setFormData((prev) => ({ ...prev, phone: e.target.value }));
                    if (errors.phone) setErrors((prev) => ({ ...prev, phone: "" }));
                  }}
                  placeholder="+234 800 000 0000"
                  className="input"
                  disabled={isPending}
                />
              </FormField>

              <FormField label="Department" error={errors.department}>
                <input
                  type="text"
                  list="hr-departments-list"
                  value={formData.department}
                  onChange={(e) => {
                    setFormData((prev) => ({ ...prev, department: e.target.value }));
                    if (errors.department) setErrors((prev) => ({ ...prev, department: "" }));
                  }}
                  placeholder="e.g., Sales, IT"
                  className="input"
                  disabled={isPending}
                />
                <datalist id="hr-departments-list">
                  {activeNames(departments).map((n) => <option key={n} value={n} />)}
                </datalist>
              </FormField>
            </div>

            {/* Job Title */}
            <FormField label="Job Title" error={errors.job_title}>
              <input
                type="text"
                list="hr-job-titles-list"
                value={formData.job_title}
                onChange={(e) => {
                  setFormData((prev) => ({ ...prev, job_title: e.target.value }));
                  if (errors.job_title) setErrors((prev) => ({ ...prev, job_title: "" }));
                }}
                placeholder="e.g., Senior Manager"
                className="input"
                disabled={isPending}
              />
              <datalist id="hr-job-titles-list">
                {activeNames(jobTitles).map((n) => <option key={n} value={n} />)}
              </datalist>
            </FormField>

            {/* Roles */}
            <FormField
              label="Assign Roles"
              error={errors.role_ids}
              required
            >
              <div className="space-y-2">
                {availableRoles.length === 0 ? (
                  <p className="text-sm text-slate-500 italic">No roles available</p>
                ) : (
                  availableRoles.map((role) => (
                    <label
                      key={role.id}
                      className="flex items-center gap-3 p-2.5 rounded-lg border border-slate-200 hover:bg-slate-50 cursor-pointer transition-colors"
                    >
                      <input
                        type="checkbox"
                        checked={formData.role_ids.includes(role.id)}
                        onChange={() => handleRoleToggle(role.id)}
                        disabled={isPending}
                        className="w-4 h-4 rounded border-slate-300 text-blue-600 focus:ring-2 focus:ring-blue-500"
                      />
                      <div className="flex-1">
                        <p className="text-sm font-medium text-slate-900">{role.name}</p>
                        <p className="text-xs text-slate-500">{role.slug}</p>
                      </div>
                      {role.color && (
                        <div
                          className="w-3 h-3 rounded-full"
                          style={{ backgroundColor: role.color }}
                          title={role.color}
                        />
                      )}
                    </label>
                  ))
                )}
              </div>
            </FormField>

            {/* Section — only for teaching roles, and then required */}
            {needsSection && (
              <FormField label="Section" error={errors.section_ids} required>
                <div className="flex flex-wrap gap-2">
                  {sections.length === 0 ? (
                    <p className="text-sm text-slate-500 italic">No sections set up yet</p>
                  ) : sections.map((sec) => (
                    <label
                      key={sec.id}
                      className={`flex items-center gap-2 px-3 py-2 rounded-lg border cursor-pointer text-sm font-medium transition-colors ${
                        formData.section_ids.includes(sec.id) ? "border-brand-600 bg-brand-50 text-brand-700" : "border-slate-200 text-slate-700 hover:bg-slate-50"
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={formData.section_ids.includes(sec.id)}
                        onChange={() => handleSectionToggle(sec.id)}
                        disabled={isPending}
                        className="w-4 h-4 rounded border-slate-300"
                      />
                      {sec.name}
                    </label>
                  ))}
                </div>
                <p className="text-[11px] text-slate-400 mt-1">Decides which report menus and pupils this teacher sees. Pick more than one if they teach across sections.</p>
              </FormField>
            )}

            {/* Subjects — optional; taught in every class of the subject's section (refine later on Teaching Assignments) */}
            {needsSection && formData.section_ids.length > 0 && (
              <FormField label="Subjects taught">
                <div className="flex flex-wrap gap-2">
                  {subjectsForSections.length === 0 ? (
                    <p className="text-sm text-slate-500 italic">No subjects in the chosen section(s) yet</p>
                  ) : subjectsForSections.map((sub) => (
                    <label key={sub.id}
                      className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border cursor-pointer text-sm transition-colors ${
                        formData.subject_ids.includes(sub.id) ? "border-brand-600 bg-brand-50 text-brand-700" : "border-slate-200 text-slate-700 hover:bg-slate-50"}`}>
                      <input type="checkbox" className="w-4 h-4 rounded border-slate-300" disabled={isPending}
                        checked={formData.subject_ids.includes(sub.id)}
                        onChange={() => setFormData((prev) => ({ ...prev, subject_ids: prev.subject_ids.includes(sub.id) ? prev.subject_ids.filter((x) => x !== sub.id) : [...prev.subject_ids, sub.id] }))} />
                      {sub.name}
                    </label>
                  ))}
                </div>
                <p className="text-[11px] text-slate-400 mt-1">Optional. Each subject is taught in all classes of its section; narrow it later under Teachers → Teaching Assignments.</p>
              </FormField>
            )}

            {/* Actions */}
            <div className="flex gap-3 pt-4 border-t border-slate-200">
              <button
                type="button"
                onClick={onClose}
                className="flex-1 btn-secondary"
                disabled={isPending}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="flex-1 btn-primary gap-2 flex items-center justify-center"
                disabled={isPending}
              >
                {isPending && <Loader2 size={16} className="animate-spin" />}
                {isPending ? "Creating..." : "Create User"}
              </button>
            </div>
          </form>
        </div>
      </div>
    </>
  );
}

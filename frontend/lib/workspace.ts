import type { IndustryType, Organization } from "@/types";

export type WorkspaceModule = "school" | "business" | "hospital";

export interface WorkspaceDefinition {
  type: IndustryType;
  label: string;
  primaryModule: WorkspaceModule | null;
  modules: string[];
  permissionScopes: string[];
}

const MODULE_WORKSPACE_SCOPES: Record<string, IndustryType> = {
  school: "school",
  attendance: "school",
  behaviour: "school",
  cbt: "school",
  classroom: "school",
  clubs: "school",
  exams: "school",
  fees: "school",
  feedback: "school",
  journals: "school",
  library: "school",
  parents: "school",
  results: "school",
  sms: "school",
  subjects: "school",
  teachers: "school",
  timetable: "school",
  transport: "school",
  tuckshop: "school",
  hospital: "hospital",
  admissions: "hospital",
  appointments: "hospital",
  billing: "hospital",
  doctors: "hospital",
  emr: "hospital",
  lab: "hospital",
  nurses: "hospital",
  patients: "hospital",
  pharmacy: "hospital",
  prescriptions: "hospital",
  wards: "hospital",
  business: "business",
  customers: "business",
  crm: "business",
  departments: "business",
  employees: "business",
  expenses: "business",
  finance: "business",
  inventory: "business",
  invoices: "business",
  payroll: "business",
  pos: "business",
  procurement: "business",
  projects: "business",
  sales: "business",
};

export const WORKSPACE_REGISTRY: Record<IndustryType, WorkspaceDefinition> = {
  school: {
    type: "school",
    label: "School",
    primaryModule: "school",
    modules: [
      "school", "attendance", "behaviour", "cbt", "classroom", "clubs", "exams",
      "fees", "feedback", "journals", "library", "parents", "results", "sms",
      "subjects", "teachers", "timetable", "transport", "tuckshop", "hr", "leave",
      "analytics",
    ],
    permissionScopes: ["school"],
  },
  business: {
    type: "business",
    label: "Business",
    primaryModule: "business",
    modules: [
      "business", "customers", "crm", "departments", "employees", "expenses",
      "finance", "inventory", "invoices", "payroll", "pos", "procurement",
      "projects", "sales", "hr", "leave", "analytics",
    ],
    permissionScopes: ["business", "payroll", "finance", "inventory", "crm"],
  },
  hospital: {
    type: "hospital",
    label: "Hospital",
    primaryModule: "hospital",
    modules: [
      "hospital", "admissions", "appointments", "billing", "doctors", "emr", "lab",
      "nurses", "patients", "pharmacy", "prescriptions", "wards", "hr", "leave",
      "analytics",
    ],
    permissionScopes: ["hospital"],
  },
  hybrid: {
    type: "hybrid",
    label: "Multi-Industry",
    primaryModule: null,
    modules: [
      "school", "business", "hospital", "hr", "leave", "analytics", "payroll",
      "inventory", "finance", "crm", "sms", "transport", "library", "appointments",
      "emr", "billing", "lab", "pharmacy", "wards", "invoices", "procurement",
      "projects",
    ],
    permissionScopes: ["school", "business", "hospital", "payroll", "finance", "inventory", "crm"],
  },
};

export function workspaceFor(industry: IndustryType | undefined | null): WorkspaceDefinition {
  return WORKSPACE_REGISTRY[industry ?? "hybrid"] ?? WORKSPACE_REGISTRY.hybrid;
}

export function effectiveModulesForOrg(org: Organization | null | undefined): string[] {
  if (!org) return [];
  const configured = org.modules_enabled ?? [];
  const workspace = workspaceFor(org.industry);
  if (workspace.type === "hybrid") {
    return configured.filter((module) => module in MODULE_WORKSPACE_SCOPES || workspace.modules.includes(module));
  }
  return configured.filter((module) => {
    const owner = MODULE_WORKSPACE_SCOPES[module];
    if (owner) return owner === workspace.type;
    return workspace.modules.includes(module);
  });
}

export function moduleAllowedForOrg(org: Organization | null | undefined, module: WorkspaceModule): boolean {
  if (!org) return true;
  const workspace = workspaceFor(org.industry);
  if (workspace.type === "hybrid") return effectiveModulesForOrg(org).includes(module);
  return workspace.primaryModule === module && effectiveModulesForOrg(org).includes(module);
}

export function permissionAllowedForOrg(org: Organization | null | undefined, permission: string): boolean {
  if (!org) return true;
  const namespace = permission.split(":")[0];
  const workspace = workspaceFor(org.industry);
  if (workspace.type === "hybrid") return true;
  if (!WORKSPACE_REGISTRY.hybrid.permissionScopes.includes(namespace)) return true;
  return workspace.permissionScopes.includes(namespace);
}

export function isSchoolRoleShell(org: Organization | null | undefined): boolean {
  return moduleAllowedForOrg(org, "school");
}

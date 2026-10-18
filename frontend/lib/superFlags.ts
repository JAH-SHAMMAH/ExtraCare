// Which pages each Super Settings switch controls. One table, read by the sidebar
// AND the route guard, so a switched-off page is both hidden and unreachable by URL.
// `when` is the switch position that makes the page AVAILABLE.
export interface FlagRoute { prefix: string; flag: string; when: boolean; label: string }

export const FLAG_ROUTES: FlagRoute[] = [
  { prefix: "/dashboard/modules/school/biometric", flag: "school_biometric", when: true, label: "School Biometric Attendance" },
  { prefix: "/dashboard/modules/school/timetable/subject-attendance", flag: "subject_attendance", when: true, label: "Subject Attendance" },
  { prefix: "/dashboard/modules/school/tuckshop", flag: "open_store_for_parents", when: true, label: "Open Store For Parents" },
  { prefix: "/dashboard/modules/office/restaurant", flag: "module_restaurant", when: true, label: "Restaurant module" },
  { prefix: "/dashboard/modules/office/empowerment", flag: "module_empowerment", when: true, label: "Empowerment module" },
  { prefix: "/dashboard/modules/office/suppliers", flag: "module_suppliers", when: true, label: "Suppliers module" },
  { prefix: "/dashboard/modules/office/serviceinvoices", flag: "module_serviceinvoices", when: true, label: "Service Invoices module" },
  { prefix: "/dashboard/modules/office/offlineinvoices", flag: "module_offlineinvoices", when: true, label: "Offline Invoices module" },
  { prefix: "/dashboard/modules/office/spa", flag: "module_spa", when: true, label: "Spa Services module" },
  { prefix: "/dashboard/modules/office/storeappointments", flag: "module_storeappointments", when: true, label: "Store Appointment Manager module" },
  { prefix: "/dashboard/modules/office/procurement", flag: "module_procurement", when: true, label: "Procurement module" },
  { prefix: "/dashboard/modules/office/livestock", flag: "module_livestock", when: true, label: "Livestock module" },
  { prefix: "/dashboard/modules/office/rentals", flag: "module_rentals", when: true, label: "Rentals module" },
  { prefix: "/dashboard/modules/office/funfair", flag: "module_funfair", when: true, label: "Fun Fair module" },
  { prefix: "/dashboard/modules/office/ledger", flag: "module_ledger", when: true, label: "General Ledger module" },
  { prefix: "/dashboard/modules/office/imprest", flag: "module_imprest", when: true, label: "Imprest module" },
  { prefix: "/dashboard/modules/office/debtmemo", flag: "module_debtmemo", when: true, label: "Debt Memo module" },
  { prefix: "/dashboard/modules/office/customers", flag: "module_customers", when: true, label: "All Customers module" },
  { prefix: "/dashboard/modules/office/whatsapp", flag: "module_whatsapp", when: true, label: "WhatsApp module" },
  { prefix: "/dashboard/modules/office/clubattendance", flag: "module_clubattendance", when: true, label: "Club Attendance module" },
  { prefix: "/dashboard/modules/office/commbook", flag: "module_commbook", when: true, label: "Communication Book module" },
  { prefix: "/dashboard/communication-book", flag: "module_commbook", when: true, label: "Communication Book module" },
  { prefix: "/dashboard/my-children/store-appointments", flag: "module_storeappointments", when: true, label: "Store Appointment Manager module" },
];

export function isSuperUser(user: { primary_role?: string; permissions?: string[] } | null | undefined): boolean {
  return !!user && (user.primary_role === "super_admin" || !!user.permissions?.includes("*"));
}

/** The switch blocking `pathname`, if any. Undefined flags (not loaded yet) never block.
 *  Staff keep the store (`open_store_for_parents` only closes it to families). */
export function blockingFlag(
  pathname: string,
  flags: Record<string, boolean> | undefined,
  opts: { staff?: boolean } = {},
): FlagRoute | null {
  if (!flags) return null;
  let best: FlagRoute | null = null;
  for (const r of FLAG_ROUTES) {
    if (pathname === r.prefix || pathname.startsWith(r.prefix + "/")) {
      if (!best || r.prefix.length > best.prefix.length) best = r;
    }
  }
  if (!best) return null;
  if (best.flag === "open_store_for_parents" && opts.staff) return null;
  const v = flags[best.flag];
  if (v === undefined) return null;
  return v === best.when ? null : best;
}

// ── Student / teacher dashboard switches and per-role hidden pages ──────────
// Only the pages that exist in the app are listed; the other dashboard switches
// are stored and shown in Super Settings.
export const STUDENT_FLAG_ROUTES: { flag: string; label: string; prefixes: string[] }[] = [
  { flag: "show_ctb_link", label: "Show CTB Link", prefixes: ["/dashboard/my-exams"] },
  { flag: "show_eclassroom_link", label: "Show eClassroom Link", prefixes: ["/dashboard/my-live-classes", "/dashboard/modules/eclassroom"] },
  { flag: "show_teacher_rating_tab", label: "Show Teacher Rating Tab", prefixes: ["/dashboard/my-teachers"] },
  { flag: "show_results", label: "Show Results", prefixes: ["/dashboard/modules/school/report-cards"] },
  { flag: "show_assignment", label: "Show Assignment", prefixes: ["/dashboard/modules/school/eclassroom"] },
  { flag: "show_timetable", label: "Show Timetable", prefixes: ["/dashboard/my-timetable"] },
  { flag: "show_chat", label: "Show Chat", prefixes: ["/messenger"] },
  { flag: "show_calendar", label: "Show Calendar", prefixes: ["/dashboard/modules/school/calendar"] },
  { flag: "show_medical_reports", label: "Show Medical Reports", prefixes: ["/dashboard/modules/school/medicals"] },
  { flag: "show_tuckshop_record", label: "Show Tuck Shop Record", prefixes: ["/dashboard/modules/school/tuckshop"] },
];
export const TEACHER_FLAG_ROUTES = [
  { flag: "show_house_point_entry_link", label: "Show House Point Entry Link", prefixes: ["/dashboard/modules/school/point-entry"] },
];

const under = (path: string, prefix: string) => path === prefix || path.startsWith(prefix + "/");

export interface UiShape {
  flags?: Record<string, boolean>; student_dashboard?: Record<string, boolean>;
  teacher_dashboard?: Record<string, boolean>; hidden_hrefs?: string[];
}

/** Why `pathname` is switched off for this viewer, or null. One rule for the sidebar and the URL guard. */
export function blockingUi(
  pathname: string,
  ui: UiShape | undefined,
  view: { staff?: boolean; student?: boolean; teacher?: boolean } = {},
): { label: string } | null {
  if (!ui) return null;
  const f = blockingFlag(pathname, ui.flags, { staff: view.staff });
  if (f) return { label: f.label };
  if (view.student) {
    for (const r of STUDENT_FLAG_ROUTES) {
      if (ui.student_dashboard?.[r.flag] === false && r.prefixes.some((p) => under(pathname, p))) return { label: r.label };
    }
  }
  if (view.teacher) {
    for (const r of TEACHER_FLAG_ROUTES) {
      if (ui.teacher_dashboard?.[r.flag] === false && r.prefixes.some((p) => under(pathname, p))) return { label: r.label };
    }
  }
  for (const h of ui.hidden_hrefs ?? []) {
    const base = h.split("?")[0];
    if (under(pathname, base)) return { label: "Module Permissions Manager" };
  }
  return null;
}

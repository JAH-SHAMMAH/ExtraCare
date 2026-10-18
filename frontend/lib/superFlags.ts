// Which pages each Super Settings switch controls. One table, read by the sidebar
// AND the route guard, so a switched-off page is both hidden and unreachable by URL.
// `when` is the switch position that makes the page AVAILABLE.
export interface FlagRoute { prefix: string; flag: string; when: boolean; label: string }

export const FLAG_ROUTES: FlagRoute[] = [
  { prefix: "/dashboard/modules/school/biometric", flag: "school_biometric", when: true, label: "School Biometric Attendance" },
  { prefix: "/dashboard/modules/school/timetable/subject-attendance", flag: "subject_attendance", when: true, label: "Subject Attendance" },
  { prefix: "/dashboard/modules/school/tuckshop", flag: "open_store_for_parents", when: true, label: "Open Store For Parents" },
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

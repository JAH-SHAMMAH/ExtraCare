import { PlannedFeature } from "@/components/PlannedFeature";

export default function WeekEntriesPage() {
  return (
    <PlannedFeature
      section="Admin Management"
      title="Manage Week Entries"
      description="Define the academic weeks within each term — the calendar backbone that attendance, timetabling, weekly remarks and reports reference."
      points={[
        "Create / edit / lock weeks per term",
        "Mark holidays and non-teaching weeks",
        "Used by attendance and weekly remarks once wired to the backend",
      ]}
    />
  );
}

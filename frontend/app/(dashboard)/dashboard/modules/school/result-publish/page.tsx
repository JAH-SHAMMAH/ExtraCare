import { PlannedFeature } from "@/components/PlannedFeature";

export default function ResultPublishPage() {
  return (
    <PlannedFeature
      section="Admin Management"
      title="Result Publish Helper"
      description="Bulk-publish or unpublish student results and report cards for a term, so parents and students only see finalised grades."
      points={[
        "Publish / unpublish results per class or term in one action",
        "Guard against exposing draft grades",
        "Complements the existing Report Workflow (per-report approval)",
      ]}
      action={{ href: "/dashboard/modules/school/report-workflow", label: "Open Report Workflow" }}
    />
  );
}

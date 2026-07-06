import { PlannedFeature } from "@/components/PlannedFeature";

export default function UserRolesPage() {
  return (
    <PlannedFeature
      section="Admin Management"
      title="Manage User Roles & Password"
      description="Assign roles to staff/admins and reset their passwords. Role assignment already works today via Access Control; admin-initiated password reset is the piece still to be built (it needs a new backend endpoint)."
      points={[
        "Role assignment — available now under Access Control",
        "Admin password reset — planned (new backend endpoint)",
        "View each role's exact permissions",
      ]}
      action={{ href: "/dashboard/hrm/access-control", label: "Open Access Control (role assignment)" }}
    />
  );
}

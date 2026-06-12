import type { Metadata } from "next";
import { IndustryLanding } from "@/components/marketing/IndustryLanding";
import { canonical, faqSchema, INDUSTRY_LANDING_PAGES, softwareSchema } from "@/lib/seo";

const page = INDUSTRY_LANDING_PAGES[0];

const faqs = [
  {
    question: "Can the Fairview School Portal manage student records, attendance, and fees together?",
    answer:
      "Yes. The portal keeps student profiles, class records, attendance, exams, results, fee tracking, timetable, transport, CBT, library, and academic reports inside one school system.",
  },
  {
    question: "Is this suitable for schools in Nigeria?",
    answer:
      "The Fairview School Portal is built for Nigerian schools and supports practical school record keeping, parent communication, academic reporting, fee workflows, and WAEC/JAMB preparation use cases.",
  },
  {
    question: "Who can sign in to the portal?",
    answer:
      "Administrators, teachers, parents, students, and school staff with a Fairview School account. Access is restricted to verified school accounts only.",
  },
];

export const metadata: Metadata = {
  title: "School Management Software and School ERP Nigeria",
  description: page.description,
  keywords: [...page.keywords],
  alternates: { canonical: canonical(page.path) },
  openGraph: {
    title: page.title,
    description: page.description,
    url: canonical(page.path),
    siteName: "Fairview School Portal",
    type: "website",
  },
};

export default function SchoolsLandingPage() {
  return (
    <IndustryLanding
      eyebrow="School management software"
      title="Fairview School Portal"
      description={page.description}
      primaryCta="Sign in"
      accent="indigo"
      previewMetrics={[
        { label: "Students", value: "1,240" },
        { label: "Attendance", value: "94%" },
        { label: "Classes", value: "42" },
        { label: "Fees", value: "86%" },
      ]}
      features={[
        {
          title: "Academic records",
          body: "Manage students, teachers, parents, classes, subjects, exams, results, and report cards in one focused school system.",
        },
        {
          title: "Daily operations",
          body: "Track attendance, timetable, transport, library, hostel, fees, SMS, CBT, live classes, and school communications.",
        },
        {
          title: "Enhanced school HR",
          body: "Use the shared HR engine for staff profiles, leave, birthdays, payroll-ready records, and school-specific staff structures.",
        },
        {
          title: "Secure tenant isolation",
          body: "Permissions are scoped to the school workspace so teachers, parents, students, and staff see only education modules.",
        },
      ]}
      modules={[
        { label: "Students and Parents", detail: "Profiles, guardians, attendance history, academic records, and communication trails." },
        { label: "Exams and Results", detail: "Gradebook, CBT, WAEC/JAMB prep, report cards, and academic performance reporting." },
        { label: "Fees and Operations", detail: "Fee management, transport, library, hostel, timetable, SMS, and school activity records." },
        { label: "School HR", detail: "Staff records, departments, leave, attendance, and HR workflows powered by the shared HR engine." },
      ]}
      outcomes={[
        "Keep complete school records without spreadsheets.",
        "Give administrators one clean view of academic and operational health.",
        "Separate teacher, parent, student, and staff permissions.",
        "Prepare for growth without rebuilding your school software stack.",
      ]}
      faqs={faqs}
      schema={[
        softwareSchema({
          name: page.title,
          description: page.description,
          path: page.path,
          category: "SchoolManagementSystem",
          keywords: page.keywords,
        }),
        faqSchema(faqs),
      ]}
    />
  );
}

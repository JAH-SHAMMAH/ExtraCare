/**
 * OwnReportCardsView -- the page a pupil or a parent gets on Report Cards.
 *
 * Driven through the page's default export so the branch condition is under
 * test too: a caller WITHOUT the staff scope `school:reports:read` must land
 * here, whatever their role slug. The data hooks are mocked; access itself is
 * enforced by the API and covered in backend/tests/test_own_report_card_scope.py.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

type Child = { id: string; first_name: string; last_name: string };

const state = {
  children: [] as Child[],
  activeRole: "parent" as string | null,
  perms: [] as string[],
};

vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams() }));

vi.mock("@/lib/store", () => ({
  useAuthStore: () => ({ user: { roles: [{ slug: "parent-boarding" }] }, activeRole: state.activeRole }),
}));

vi.mock("@/components/guards/PermissionGate", () => ({
  useHasPermission: (p: string) => state.perms.includes(p),
}));

vi.mock("@/components/branding/Brand", () => ({ PrintLetterhead: () => null }));

vi.mock("@/hooks/usePlatform", () => ({
  useTermState: () => ["First Term", () => {}],
  useTermNames: () => ["First Term", "Second Term"],
  useGradingScales: () => ({ data: [] }),
  useSections: () => ({ data: [] }),
  useTerms: () => ({ data: [] }),
}));

const mutation = { mutate: vi.fn(), isPending: false };
vi.mock("@/hooks/useSchool", () => ({
  useStudents: () => ({ data: { items: state.children }, isLoading: false }),
  // A card exists for every real child; the card names the child it was asked for.
  useReportCard: (studentId: string) => {
    const child = state.children.find((c) => c.id === studentId);
    return {
      data: child ? { student: child, subjects: [], domains: [], term: "First Term" } : undefined,
      isLoading: false,
    };
  },
  useClasses: () => ({ data: { items: [] } }),
  useSaveReportMeta: () => mutation,
  useSaveDomainRatings: () => mutation,
}));

import ReportCardsPage from "@/app/(dashboard)/dashboard/modules/school/report-cards/page";

const ADA: Child = { id: "stu-ada", first_name: "Ada", last_name: "Obi" };
const TOBI: Child = { id: "stu-tobi", first_name: "Tobi", last_name: "Obi" };

const cardHeading = () => screen.getByRole("heading", { level: 2 });

beforeEach(() => {
  state.children = [];
  state.activeRole = "parent";
  state.perms = ["school:reports:own:read"];
});

describe("Report Cards — own view (pupil / parent)", () => {
  it("one child: shows that child's card and no child dropdown", () => {
    state.children = [ADA];
    render(<ReportCardsPage />);

    expect(screen.queryByLabelText("Child")).not.toBeInTheDocument();
    expect(cardHeading()).toHaveTextContent("Ada Obi");
    // Parent wording, not the pupil's "My Report Card", and not the teacher desk.
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Report Cards");
    expect(screen.queryByPlaceholderText("Search students...")).not.toBeInTheDocument();
  });

  it("two children: the dropdown lists both and switches the card", () => {
    state.children = [ADA, TOBI];
    render(<ReportCardsPage />);

    const picker = screen.getByLabelText("Child") as HTMLSelectElement;
    expect(Array.from(picker.options).map((o) => o.value)).toEqual([ADA.id, TOBI.id]);
    expect(cardHeading()).toHaveTextContent("Ada Obi");

    fireEvent.change(picker, { target: { value: TOBI.id } });
    expect(cardHeading()).toHaveTextContent("Tobi Obi");
  });

  it("zero children: the empty message, and no card is requested for anyone", () => {
    state.children = [];
    render(<ReportCardsPage />);

    expect(screen.getByText("No report card available")).toBeInTheDocument();
    expect(screen.getByText(/the report is not published/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Child")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { level: 2 })).not.toBeInTheDocument();
  });

  it("a pupil keeps the pupil wording", () => {
    state.children = [ADA];
    state.activeRole = "student";
    render(<ReportCardsPage />);

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("My Report Card");
  });

  it("a caller WITH the staff scope gets the teacher desk instead", () => {
    state.children = [ADA, TOBI];
    state.perms = ["school:reports:read"];
    render(<ReportCardsPage />);

    expect(screen.getByPlaceholderText("Search students...")).toBeInTheDocument();
    expect(screen.queryByLabelText("Child")).not.toBeInTheDocument();
  });
});

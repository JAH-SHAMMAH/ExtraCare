import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

const slots = [
  { id: "s1", name: "Teacher Comment", comment_type: "long", max_length: 200, admin_only: false },
  { id: "s2", name: "Director Note", comment_type: "short", max_length: null, admin_only: true },
];
vi.mock("@/hooks/usePlatform", () => ({ useCommentTypes: () => ({ data: slots, isLoading: false }) }));
const grid = vi.fn((props: any) => <div data-testid="grid">{props.label}|{props.commentTypeId}|{props.maxLength}</div>);
vi.mock("@/components/reports/ReportCardPrint", () => ({ CommentGridTab: (p: any) => grid(p) }));

import { NonAssessmentTab } from "@/components/reports/NonAssessmentTab";

describe("NonAssessmentTab", () => {
  it("lets an admin pick any slot and opens that slot's grid", () => {
    render(<NonAssessmentTab />);
    expect(screen.getByText(/Director Note \(admin only\)/)).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Comment"), { target: { value: "s1" } });
    expect(screen.getByTestId("grid").textContent).toBe("Teacher Comment|s1|200");
  });

  it("hides admin-only slots from teachers", () => {
    render(<NonAssessmentTab adminOnly={false} />);
    expect(screen.getByText("Teacher Comment")).toBeTruthy();
    expect(screen.queryByText(/Director Note/)).toBeNull();
  });
});

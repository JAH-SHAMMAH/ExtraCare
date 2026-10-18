import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

const mutate = vi.hoisted(() => vi.fn());
vi.mock("@/hooks/useSchool", () => ({
  useMyTeachers: () => ({ isLoading: false, error: null, data: [
    { teacher_id: "t1", name: "Ada Obi", subjects: ["Maths"], class_teacher: true, my_rating: null, my_comment: null },
  ] }),
  useRateMyTeacher: () => ({ mutate, isPending: false }),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import Page from "@/app/(dashboard)/dashboard/my-teachers/page";

describe("Rate My Teachers", () => {
  it("lists my teacher and submits a star rating", () => {
    render(<Page />);
    expect(screen.getByText("Ada Obi")).toBeTruthy();
    const submit = screen.getByRole("button", { name: /submit rating/i }) as HTMLButtonElement;
    expect(submit.disabled).toBe(true);
    fireEvent.click(screen.getByLabelText("4 stars"));
    fireEvent.click(screen.getByLabelText(/anonymously/i));
    fireEvent.click(submit);
    expect(mutate.mock.calls[0][0]).toMatchObject({ teacher_id: "t1", rating: 4, anonymous: true });
  });
});

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import TeacherGuidePage from "@/app/(dashboard)/dashboard/teacher-guide/page";
import { TEACHER_GUIDE } from "@/lib/teacherGuide";

describe("Teacher guide", () => {
  it("shows every section with its steps", () => {
    render(<TeacherGuidePage />);
    expect(screen.getByRole("heading", { name: /teacher quick guide/i })).toBeTruthy();
    TEACHER_GUIDE.forEach((s) => expect(screen.getByText(s.title)).toBeTruthy());
    expect(screen.getByText(/mark attendance first thing/i)).toBeTruthy();
  });
});

import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { QuickGuideButton } from "@/components/guide/QuickGuide";
import { GUIDE_TOPICS, searchTopics } from "@/lib/quickGuide";
import { useAuthStore } from "@/lib/store";

describe("Quick Guide", () => {
  it("admin sees the button, opens a topic with steps", () => {
    useAuthStore.setState({ activeRole: "admin" } as any);
    render(<QuickGuideButton />);
    fireEvent.click(screen.getByText("Quick Guide"));
    fireEvent.click(screen.getByText("Attendance, check-in and parent alerts"));
    expect(screen.getByText(/arrived at school at 7:32 AM/)).toBeTruthy();
  });
  it("teacher, parent and student never see it", () => {
    for (const r of ["teacher", "parent", "student"]) {
      useAuthStore.setState({ activeRole: r } as any);
      const { container, unmount } = render(<QuickGuideButton />);
      expect(container.textContent).toBe("");
      unmount();
    }
  });
  it("search narrows topics and content is substantial", () => {
    expect(searchTopics("reset password").some((t) => t.id === "users-roles")).toBe(true);
    expect(searchTopics("zzzz")).toHaveLength(0);
    expect(GUIDE_TOPICS.length).toBeGreaterThanOrEqual(15);
    for (const t of GUIDE_TOPICS) {
      expect(t.steps.length).toBeGreaterThanOrEqual(4);
      if (t.href) expect(t.href.startsWith("/dashboard")).toBe(true);
    }
  });
});

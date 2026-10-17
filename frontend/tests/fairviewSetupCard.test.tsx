import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const setup = vi.fn();
vi.mock("@/lib/api", () => ({ platformApi: { fairviewSetup: (a: boolean) => setup(a) } }));
import { FairviewSetupCard } from "@/components/reports/FairviewSetupCard";

describe("FairviewSetupCard", () => {
  it("previews first, and only applies after the preview", async () => {
    setup.mockResolvedValueOnce({ applied: false, domains: { a: { added: ["x", "y"] } }, columns: { added: ["c"] },
      marks: { scores_added: 3, legacy_assessments: 1, retired: true, problems: [] } });
    render(<FairviewSetupCard />);
    expect(screen.queryByText("Apply")).toBeNull();
    fireEvent.click(screen.getByText("Preview"));
    await waitFor(() => screen.getByText(/nothing changed yet/));
    expect(setup).toHaveBeenLastCalledWith(false);
    setup.mockResolvedValueOnce({ applied: true, domains: {}, columns: { added: [] }, marks: null });
    fireEvent.click(screen.getByText("Apply"));
    await waitFor(() => screen.getByText("Done."));
    expect(setup).toHaveBeenLastCalledWith(true);
  });
});

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const mutateAsync = vi.fn().mockResolvedValue({});
let grid: any;
vi.mock("@/hooks/useSchool", () => ({
  useClassDomainRatings: () => ({ data: grid, isLoading: false, isError: false }),
  useSaveDomainRatings: () => ({ mutateAsync, isPending: false }),
}));
vi.mock("@/lib/api", () => ({ uploadApi: { reportPhoto: vi.fn().mockResolvedValue({ url: "https://cdn.example/p.jpg" }) } }));
vi.mock("sonner", () => ({ toast: { error: vi.fn() } }));

import { DomainRatingsEntry } from "@/components/reports/DomainRatingsEntry";

beforeEach(() => mutateAsync.mockClear());

describe("DomainRatingsEntry", () => {
  it("offers the domain's own key and sends ONLY the changed cell", async () => {
    grid = {
      domains: [
        { domain_id: "d1", name: "Punctuality", domain_type: "affective", options: ["5", "4", "3"] },
        { domain_id: "d2", name: "Neatness", domain_type: "affective", options: ["5", "4", "3"] },
      ],
      students: [{ student_id: "s1", student_name: "Ada Obi", ratings: { d2: { rating: "4", comment: null, photo_url: null } } }],
    };
    render(<DomainRatingsEntry classId="c" termId="t" canWrite />);
    const selects = screen.getAllByRole("combobox");
    expect(selects).toHaveLength(2);
    expect(Array.from((selects[0] as HTMLSelectElement).options).map((o) => o.value)).toEqual(["", "5", "4", "3"]);
    expect((selects[1] as HTMLSelectElement).value).toBe("4");           // saved value shows
    fireEvent.change(selects[0], { target: { value: "5" } });
    fireEvent.click(screen.getByRole("button", { name: /Save/ }));
    await waitFor(() => expect(mutateAsync).toHaveBeenCalledTimes(1));
    const sent = mutateAsync.mock.calls[0][0];
    expect(sent.student_id).toBe("s1");
    expect(sent.data.ratings).toEqual([{ domain_id: "d1", rating: "5", comment: null }]);   // d2 untouched
  });

  it("nursery: writes an achievement and attaches a picture without dropping either", async () => {
    grid = {
      domains: [
        { domain_id: "a1", name: "Literacy", domain_type: "eyfs_area", options: [] },
        { domain_id: "g1", name: "Writing", domain_type: "eyfs_goal", parent_domain_id: "a1", options: [] },
      ],
      students: [{ student_id: "s1", student_name: "Ada Obi", ratings: {} }],
    };
    const { container } = render(<DomainRatingsEntry classId="c" termId="t" canWrite />);
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "s1" } });
    fireEvent.change(screen.getByPlaceholderText(/What this child can do/), { target: { value: "Writes her name" } });
    fireEvent.change(container.querySelector('input[type="file"]') as HTMLInputElement,
      { target: { files: [new File(["x"], "w.jpg", { type: "image/jpeg" })] } });
    await waitFor(() => expect(container.querySelector('img[src="https://cdn.example/p.jpg"]')).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: /Save/ }));
    await waitFor(() => expect(mutateAsync).toHaveBeenCalled());
    expect(mutateAsync.mock.calls[0][0].data.ratings).toEqual([
      { domain_id: "g1", rating: null, comment: "Writes her name", photo_url: "https://cdn.example/p.jpg" }]);
  });

});

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Pagination } from "@/components/ui/Pagination";

describe("Pagination", () => {
  it("renders nothing when only one page", () => {
    const { container } = render(
      <Pagination page={1} totalPages={1} total={5} pageSize={10} onPageChange={() => {}} />
    );
    expect(container.firstChild).toBeNull();
  });

  it("shows correct range text", () => {
    render(<Pagination page={2} totalPages={5} total={50} pageSize={10} onPageChange={() => {}} />);
    expect(screen.getByText("11")).toBeInTheDocument();
    expect(screen.getByText("20")).toBeInTheDocument();
    expect(screen.getByText("50")).toBeInTheDocument();
  });

  it("calls onPageChange when a page number is clicked", () => {
    const onPageChange = vi.fn();
    render(<Pagination page={1} totalPages={5} total={50} pageSize={10} onPageChange={onPageChange} />);
    fireEvent.click(screen.getByText("3"));
    expect(onPageChange).toHaveBeenCalledWith(3);
  });

  it("disables previous button on first page", () => {
    const onPageChange = vi.fn();
    const { container } = render(
      <Pagination page={1} totalPages={5} total={50} pageSize={10} onPageChange={onPageChange} />
    );
    const buttons = container.querySelectorAll("button");
    // first button is chevron left
    expect((buttons[0] as HTMLButtonElement).disabled).toBe(true);
  });

  it("disables next button on last page", () => {
    const { container } = render(
      <Pagination page={5} totalPages={5} total={50} pageSize={10} onPageChange={() => {}} />
    );
    const buttons = container.querySelectorAll("button");
    // last button is chevron right
    expect((buttons[buttons.length - 1] as HTMLButtonElement).disabled).toBe(true);
  });

  it("limits visible page numbers to 5", () => {
    render(<Pagination page={5} totalPages={20} total={200} pageSize={10} onPageChange={() => {}} />);
    // Should show 5 page buttons (e.g., 3,4,5,6,7). Total buttons = 5 pages + prev + next = 7
    const pageButtons = screen.getAllByRole("button").filter((b) => /^\d+$/.test(b.textContent || ""));
    expect(pageButtons.length).toBe(5);
  });
});
